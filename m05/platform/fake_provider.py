"""Fake OpenAI-compatible provider for the m05 labs.

Endpoints: POST /v1/chat/completions, POST /v1/responses, GET /v1/models, GET /health,
admin: GET/POST /admin/config, GET /admin/stats, POST /admin/reset.

Everything is deterministic given the seed: the text, the jitter and the injected faults depend only on
(seed, request id, attempt number). Send header x-fake-request-id to make a request reproducible regardless of
concurrency, and x-fake-output-tokens to choose how many tokens the model "wants" to produce.

Start: python fake_provider.py --port 5610   (or FAKE_PORT, FAKE_SEED, FAKE_TIME_SCALE, FAKE_FAULTS as JSON)
"""
import argparse
import asyncio
import hashlib
import json
import math
import os
import random
import time
import uuid
from dataclasses import dataclass, field

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from common import estimate_prompt_tokens, estimate_tokens

LATENCY = {
    "fake-small": {"ttft_base": 0.25, "ttft_per_token": 0.0008, "tpot": 0.012},
    "fake-medium": {"ttft_base": 0.45, "ttft_per_token": 0.0010, "tpot": 0.020},
    "fake-large": {"ttft_base": 0.90, "ttft_per_token": 0.0015, "tpot": 0.035},
}
JITTER_SIGMA = 0.15
FAULT_KINDS = ("rate_limit", "error_500", "timeout", "slow", "cut")
VOCAB = ("đơn hàng giao nhận kiện phí ship hoàn tiền khách địa chỉ shipper kho trễ quận tuyến chính sách bồi thường "
         "xác nhận liên hệ mã vận đơn thời gian dự kiến hôm nay ngày mai buổi sáng buổi chiều chi nhánh yêu cầu "
         "kiểm tra cập nhật trạng thái hỗ trợ cảm ơn xin lỗi vui lòng chờ").split()


@dataclass
class Config:
    seed: int = 42
    time_scale: float = 1.0
    faults: dict = field(default_factory=dict)
    capacity: int = 0
    knee: int = 8
    load_factor: float = 0.5
    timeout_hang_s: float = 60.0
    retry_after_s: float = 2.0
    slow_factor: float = 5.0

    def update(self, data):
        for k, v in data.items():
            if k not in self.__dataclass_fields__:
                raise ValueError(f"unknown config key {k}")
            if k == "faults":
                bad = [x for x in v if x not in FAULT_KINDS]
                if bad:
                    raise ValueError(f"unknown fault kind {bad}")
                if sum(v.values()) > 1.0 + 1e-9:
                    raise ValueError("fault probabilities must sum to at most 1")
            setattr(self, k, v)


@dataclass
class Stats:
    requests: int = 0
    inflight: int = 0
    max_inflight: int = 0
    completed: int = 0
    faults: dict = field(default_factory=dict)
    status: dict = field(default_factory=dict)
    prompt_tokens: int = 0
    output_tokens: int = 0
    by_model: dict = field(default_factory=dict)


def _rng(*parts):
    return random.Random(":".join(str(p) for p in parts))


def _error(status, code, message, headers=None):
    body = {"error": {"message": message, "type": code, "code": code}}
    return JSONResponse(body, status_code=status, headers=headers or {})


def _sse(obj):
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode()


def _text_for(seed, key, n):
    rnd = _rng(seed, "text", key)
    words = [rnd.choice(VOCAB) for _ in range(n)]
    if words:
        words[0] = words[0].capitalize()
    return words


def _default_output_tokens(seed, text):
    h = hashlib.sha256(text.encode()).hexdigest()
    rnd = _rng(seed, "len", h)
    return max(5, min(2000, round(math.exp(rnd.gauss(math.log(150), 0.7)))))


def create_app(config=None):
    cfg = config or Config()
    stats = Stats()
    attempts = {}
    seq = {"n": 0}
    app = FastAPI(title="fake-provider", docs_url=None, redoc_url=None)
    app.state.config = cfg
    app.state.stats = stats

    def bump(d, k, n=1):
        d[k] = d.get(k, 0) + n

    def pick_fault(rnd):
        u = rnd.random()
        acc = 0.0
        for kind in FAULT_KINDS:
            acc += cfg.faults.get(kind, 0.0)
            if u < acc:
                return kind
        return None

    def prepare(headers, model, prompt_text, messages_tokens, max_tokens):
        if headers.get("x-fake-request-id"):
            rid = headers["x-fake-request-id"]
        else:
            seq["n"] += 1
            rid = f"auto-{seq['n']}"
        attempts[rid] = attempts.get(rid, 0) + 1
        attempt = attempts[rid]
        rnd = _rng(cfg.seed, "req", rid, attempt)
        fault = pick_fault(rnd)
        if headers.get("x-fake-output-tokens"):
            want = max(1, int(headers["x-fake-output-tokens"]))
        else:
            want = _default_output_tokens(cfg.seed, prompt_text)
        n_out = min(want, max_tokens) if max_tokens else want
        finish = "length" if (max_tokens and want > max_tokens) else "stop"
        lat = LATENCY[model]
        jitter = math.exp(rnd.gauss(0, JITTER_SIGMA))
        ttft = (lat["ttft_base"] + lat["ttft_per_token"] * messages_tokens) * jitter
        tpot = lat["tpot"] * math.exp(rnd.gauss(0, JITTER_SIGMA / 3))
        return dict(rid=rid, attempt=attempt, fault=fault, n_out=n_out, finish=finish, ttft=ttft, tpot=tpot, rnd=rnd)

    def effective(plan):
        over = max(0, stats.inflight - cfg.knee)
        tpot = plan["tpot"] * (1 + cfg.load_factor * over / max(1, cfg.knee))
        ttft = plan["ttft"]
        if plan["fault"] == "slow":
            ttft *= cfg.slow_factor
            tpot *= cfg.slow_factor
        return ttft * cfg.time_scale, tpot * cfg.time_scale

    async def early_fault(plan, model):
        fault = plan["fault"]
        if cfg.capacity and stats.inflight > cfg.capacity:
            bump(stats.faults, "capacity_429")
            return _error(429, "rate_limit_exceeded", "provider is at capacity", {"Retry-After": f"{cfg.retry_after_s:g}"})
        if fault == "rate_limit":
            bump(stats.faults, "rate_limit")
            return _error(429, "rate_limit_exceeded", "injected rate limit", {"Retry-After": f"{cfg.retry_after_s:g}"})
        if fault == "error_500":
            bump(stats.faults, "error_500")
            await asyncio.sleep(0.02 * cfg.time_scale)
            return _error(500, "server_error", "injected server error")
        if fault == "timeout":
            bump(stats.faults, "timeout")
            await asyncio.sleep(cfg.timeout_hang_s * cfg.time_scale)
            return _error(504, "timeout", "injected timeout after hanging")
        if fault in ("slow", "cut"):
            bump(stats.faults, fault)
        return None

    def finish_stats(status, model, p_tokens, o_tokens):
        bump(stats.status, str(status))
        if status == 200:
            stats.completed += 1
            stats.prompt_tokens += p_tokens
            stats.output_tokens += o_tokens
            bump(stats.by_model, model)

    def begin():
        stats.inflight += 1
        stats.max_inflight = max(stats.max_inflight, stats.inflight)

    def end():
        stats.inflight -= 1

    async def generate_stream(plan, model, words, p_tokens, make_first, make_delta, make_last, usage_chunk):
        begin()
        emitted = 0
        try:
            ttft, tpot = effective(plan)
            await asyncio.sleep(ttft)
            cut_at = max(1, len(words) // 3) if plan["fault"] == "cut" else None
            yield make_first()
            started = time.perf_counter()
            for i, w in enumerate(words):
                if cut_at is not None and i >= cut_at:
                    raise RuntimeError("injected stream cut")
                if i > 0:
                    delay = i * tpot - (time.perf_counter() - started)
                    if delay > 0.002:
                        await asyncio.sleep(delay)
                yield make_delta(w + (" " if i < len(words) - 1 else ""), i)
                emitted += 1
            yield make_last()
            if usage_chunk is not None:
                yield usage_chunk(emitted)
            yield b"data: [DONE]\n\n"
            finish_stats(200, model, p_tokens, emitted)
        except asyncio.CancelledError:
            stats.output_tokens += emitted
            bump(stats.status, "client_closed")
            raise
        except RuntimeError:
            stats.output_tokens += emitted
            bump(stats.status, "cut")
            raise
        finally:
            end()

    @app.get("/health")
    async def health():
        return {"status": "ok", "inflight": stats.inflight}

    @app.get("/v1/models")
    async def models():
        return {"object": "list", "data": [{"id": m, "object": "model", "created": 1767225600, "owned_by": "fake-provider"} for m in LATENCY]}

    @app.get("/admin/config")
    async def get_config():
        return cfg.__dict__

    @app.post("/admin/config")
    async def set_config(request: Request):
        try:
            cfg.update(await request.json())
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        return cfg.__dict__

    @app.get("/admin/stats")
    async def get_stats():
        return stats.__dict__

    @app.post("/admin/reset")
    async def reset():
        fresh = Stats()
        stats.__dict__.update(fresh.__dict__)
        attempts.clear()
        seq["n"] = 0
        return {"reset": True}

    @app.post("/v1/chat/completions")
    async def chat(request: Request):
        try:
            body = await request.json()
            messages = body["messages"]
            assert isinstance(messages, list) and messages
        except Exception:
            return _error(400, "invalid_request_error", "body must be JSON with a non-empty messages list")
        model = body.get("model", "fake-medium")
        if model not in LATENCY:
            return _error(404, "model_not_found", f"model {model} does not exist")
        p_tokens = estimate_prompt_tokens(messages)
        text = "\n".join(str(m.get("content", "")) for m in messages)
        max_tokens = body.get("max_completion_tokens") or body.get("max_tokens")
        plan = prepare(request.headers, model, text, p_tokens, max_tokens)
        stats.requests += 1
        begin()
        try:
            err = await early_fault(plan, model)
        finally:
            end()
        if err is not None:
            finish_stats(err.status_code, model, 0, 0)
            return err
        words = _text_for(cfg.seed, plan["rid"], plan["n_out"])
        cid = "chatcmpl-" + hashlib.md5(plan["rid"].encode()).hexdigest()[:16]
        created = 1767225600
        headers = {"x-request-id": plan["rid"]}
        if body.get("stream"):
            include_usage = bool((body.get("stream_options") or {}).get("include_usage"))

            def chunk(delta, finish=None, usage=None, choices=True):
                d = {"id": cid, "object": "chat.completion.chunk", "created": created, "model": model,
                     "choices": [{"index": 0, "delta": delta, "finish_reason": finish}] if choices else []}
                if usage is not None:
                    d["usage"] = usage
                return _sse(d)

            gen = generate_stream(
                plan, model, words, p_tokens,
                lambda: chunk({"role": "assistant", "content": ""}),
                lambda w, i: chunk({"content": w}),
                lambda: chunk({}, finish=plan["finish"]),
                (lambda n: chunk({}, usage={"prompt_tokens": p_tokens, "completion_tokens": n, "total_tokens": p_tokens + n}, choices=False)) if include_usage else None,
            )
            return StreamingResponse(gen, media_type="text/event-stream", headers={**headers, "Cache-Control": "no-cache"})
        begin()
        try:
            ttft, tpot = effective(plan)
            await asyncio.sleep(ttft + max(0, len(words) - 1) * tpot)
        finally:
            end()
        finish_stats(200, model, p_tokens, len(words))
        content = " ".join(words)
        return JSONResponse({
            "id": cid, "object": "chat.completion", "created": created, "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": plan["finish"]}],
            "usage": {"prompt_tokens": p_tokens, "completion_tokens": len(words), "total_tokens": p_tokens + len(words)},
        }, headers=headers)

    @app.post("/v1/responses")
    async def responses(request: Request):
        try:
            body = await request.json()
            raw = body["input"]
            messages = [{"role": "user", "content": raw}] if isinstance(raw, str) else raw
            if body.get("instructions"):
                messages = [{"role": "system", "content": body["instructions"]}] + messages
            messages = [{"role": m.get("role", "user"), "content": m["content"] if isinstance(m["content"], str) else json.dumps(m["content"], ensure_ascii=False)} for m in messages]
            assert messages
        except Exception:
            return _error(400, "invalid_request_error", "body must be JSON with input")
        model = body.get("model", "fake-medium")
        if model not in LATENCY:
            return _error(404, "model_not_found", f"model {model} does not exist")
        p_tokens = estimate_prompt_tokens(messages)
        text = "\n".join(m["content"] for m in messages)
        plan = prepare(request.headers, model, text, p_tokens, body.get("max_output_tokens"))
        stats.requests += 1
        begin()
        try:
            err = await early_fault(plan, model)
        finally:
            end()
        if err is not None:
            finish_stats(err.status_code, model, 0, 0)
            return err
        words = _text_for(cfg.seed, plan["rid"], plan["n_out"])
        rid = "resp_" + hashlib.md5(plan["rid"].encode()).hexdigest()[:20]
        mid = "msg_" + hashlib.md5(plan["rid"].encode()).hexdigest()[:20]
        created = 1767225600
        headers = {"x-request-id": plan["rid"]}

        def resp_obj(status, text_out, usage):
            return {"id": rid, "object": "response", "created_at": created, "status": status, "model": model,
                    "output": [{"type": "message", "id": mid, "status": "completed" if status == "completed" else "in_progress", "role": "assistant",
                                "content": [{"type": "output_text", "text": text_out, "annotations": []}] if text_out else []}] if status == "completed" else [],
                    "parallel_tool_calls": True, "tool_choice": "auto", "tools": [], "usage": usage, "error": None, "incomplete_details": None,
                    "instructions": None, "metadata": {}, "temperature": 1.0, "top_p": 1.0}

        def usage_obj(n):
            return {"input_tokens": p_tokens, "output_tokens": n, "total_tokens": p_tokens + n,
                    "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}}

        if body.get("stream"):
            sq = {"n": 0}

            def ev(kind, **kw):
                sq["n"] += 1
                return f"event: {kind}\ndata: {json.dumps({'type': kind, 'sequence_number': sq['n'], **kw}, ensure_ascii=False)}\n\n".encode()

            part = {"type": "output_text", "text": "", "annotations": []}
            item0 = {"type": "message", "id": mid, "status": "in_progress", "role": "assistant", "content": []}

            def first():
                return (ev("response.created", response=resp_obj("in_progress", "", None)) + ev("response.output_item.added", output_index=0, item=item0)
                        + ev("response.content_part.added", item_id=mid, output_index=0, content_index=0, part=part))

            def delta(w, i):
                return ev("response.output_text.delta", item_id=mid, output_index=0, content_index=0, delta=w, logprobs=[])

            def last():
                full = " ".join(words)
                done_part = {"type": "output_text", "text": full, "annotations": []}
                done_item = {**item0, "status": "completed", "content": [done_part]}
                return (ev("response.output_text.done", item_id=mid, output_index=0, content_index=0, text=full, logprobs=[])
                        + ev("response.content_part.done", item_id=mid, output_index=0, content_index=0, part=done_part)
                        + ev("response.output_item.done", output_index=0, item=done_item)
                        + ev("response.completed", response=resp_obj("completed", full, usage_obj(len(words)))))

            gen = generate_stream(plan, model, words, p_tokens, first, delta, last, None)
            return StreamingResponse(gen, media_type="text/event-stream", headers={**headers, "Cache-Control": "no-cache"})
        begin()
        try:
            ttft, tpot = effective(plan)
            await asyncio.sleep(ttft + max(0, len(words) - 1) * tpot)
        finally:
            end()
        finish_stats(200, model, p_tokens, len(words))
        return JSONResponse(resp_obj("completed", " ".join(words), usage_obj(len(words))), headers=headers)

    return app


def config_from_env():
    cfg = Config(seed=int(os.environ.get("FAKE_SEED", "42")), time_scale=float(os.environ.get("FAKE_TIME_SCALE", "1.0")))
    if os.environ.get("FAKE_FAULTS"):
        cfg.update({"faults": json.loads(os.environ["FAKE_FAULTS"])})
    return cfg


app = create_app(config_from_env())

if __name__ == "__main__":
    import uvicorn

    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("FAKE_PORT", "5600")))
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")
