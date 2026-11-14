import json

import pytest
from fastapi.testclient import TestClient
from openai import OpenAI

from fake_provider import Config, create_app

MSG = [{"role": "user", "content": "Đơn AT123456 của tôi đang ở đâu?"}]


def make(**kw):
    cfg = Config(time_scale=0.0, **kw)
    return TestClient(create_app(cfg)), cfg


def chat(c, rid="t1", n=40, **body):
    return c.post("/v1/chat/completions", json={"model": "fake-small", "messages": MSG, **body},
                  headers={"x-fake-request-id": rid, "x-fake-output-tokens": str(n)})


def test_chat_returns_usage_and_requested_length():
    c, _ = make()
    r = chat(c)
    assert r.status_code == 200
    d = r.json()
    assert d["usage"]["completion_tokens"] == 40
    assert d["usage"]["prompt_tokens"] > 5
    assert d["usage"]["total_tokens"] == d["usage"]["prompt_tokens"] + 40
    assert len(d["choices"][0]["message"]["content"].split()) == 40


def test_same_seed_same_text_and_different_seed_differs():
    a = chat(make(seed=7)[0]).json()["choices"][0]["message"]["content"]
    b = chat(make(seed=7)[0]).json()["choices"][0]["message"]["content"]
    c = chat(make(seed=8)[0]).json()["choices"][0]["message"]["content"]
    assert a == b and a != c


def test_max_tokens_truncates_with_finish_reason_length():
    d = chat(make()[0], n=100, max_tokens=10).json()
    assert d["usage"]["completion_tokens"] == 10
    assert d["choices"][0]["finish_reason"] == "length"


def test_default_length_depends_on_prompt_not_on_call_order():
    c, _ = make()
    r = lambda rid: c.post("/v1/chat/completions", json={"model": "fake-small", "messages": MSG}, headers={"x-fake-request-id": rid}).json()["usage"]["completion_tokens"]
    assert r("a") == r("b")


def test_streaming_chunks_and_usage():
    c, _ = make()
    with c.stream("POST", "/v1/chat/completions", json={"model": "fake-small", "messages": MSG, "stream": True, "stream_options": {"include_usage": True}},
                  headers={"x-fake-output-tokens": "12", "x-fake-request-id": "s1"}) as r:
        lines = [x for x in r.iter_lines() if x.startswith("data: ")]
    assert lines[-1] == "data: [DONE]"
    events = [json.loads(x[6:]) for x in lines[:-1]]
    text = "".join(e["choices"][0]["delta"].get("content") or "" for e in events if e["choices"])
    assert len(text.split()) == 12
    assert events[-1]["usage"]["completion_tokens"] == 12
    assert events[-2]["choices"][0]["finish_reason"] == "stop"


def test_stream_and_nonstream_same_text():
    c, _ = make()
    plain = chat(c, rid="same", n=9).json()["choices"][0]["message"]["content"]
    with c.stream("POST", "/v1/chat/completions", json={"model": "fake-small", "messages": MSG, "stream": True},
                  headers={"x-fake-output-tokens": "9", "x-fake-request-id": "same"}) as r:
        evs = [json.loads(x[6:]) for x in r.iter_lines() if x.startswith("data: {")]
    assert "".join(e["choices"][0]["delta"].get("content") or "" for e in evs if e["choices"]) == plain


def test_fault_rate_limit_has_retry_after():
    c, _ = make(faults={"rate_limit": 1.0}, retry_after_s=3)
    r = chat(c)
    assert r.status_code == 429
    assert r.headers["retry-after"] == "3"
    assert r.json()["error"]["code"] == "rate_limit_exceeded"


def test_fault_500_and_timeout_status():
    assert chat(make(faults={"error_500": 1.0})[0]).status_code == 500
    assert chat(make(faults={"timeout": 1.0}, timeout_hang_s=1)[0]).status_code == 504


def test_fault_pattern_is_deterministic_by_request_id():
    def run():
        c, _ = make(faults={"rate_limit": 0.3, "error_500": 0.2}, seed=11)
        return [chat(c, rid=f"q{i}").status_code for i in range(60)]
    a, b = run(), run()
    assert a == b
    assert 200 in a and 429 in a and 500 in a


def test_fault_rate_roughly_matches_probability():
    c, _ = make(faults={"error_500": 0.25}, seed=5)
    codes = [chat(c, rid=f"z{i}").status_code for i in range(400)]
    assert 0.17 < codes.count(500) / 400 < 0.33


def test_retry_of_same_id_draws_a_new_fault_decision():
    c, _ = make(faults={"error_500": 0.5}, seed=3)
    seen = set()
    for _ in range(12):
        seen.add(chat(c, rid="same-id").status_code)
    assert seen == {200, 500}


def test_slow_fault_multiplies_latency_model():
    from fake_provider import LATENCY
    c, cfg = make(faults={"slow": 1.0}, slow_factor=4)
    assert chat(c).status_code == 200
    assert c.get("/admin/stats").json()["faults"]["slow"] == 1


def test_admin_config_roundtrip_and_validation():
    c, cfg = make()
    r = c.post("/admin/config", json={"faults": {"error_500": 1.0}})
    assert r.status_code == 200 and cfg.faults == {"error_500": 1.0}
    assert chat(c).status_code == 500
    assert c.post("/admin/config", json={"faults": {"nope": 0.1}}).status_code == 400
    assert c.post("/admin/config", json={"bogus": 1}).status_code == 400
    assert c.post("/admin/reset").json() == {"reset": True}
    assert c.get("/admin/stats").json()["requests"] == 0


def test_stats_count_tokens_and_status():
    c, _ = make()
    chat(c, rid="a", n=10)
    chat(c, rid="b", n=20)
    s = c.get("/admin/stats").json()
    assert s["requests"] == 2 and s["completed"] == 2 and s["output_tokens"] == 30 and s["status"]["200"] == 2


def test_unknown_model_and_bad_body():
    c, _ = make()
    assert c.post("/v1/chat/completions", json={"model": "gpt-x", "messages": MSG}).status_code == 404
    assert c.post("/v1/chat/completions", json={"model": "fake-small"}).status_code == 400


def test_models_and_health():
    c, _ = make()
    assert {m["id"] for m in c.get("/v1/models").json()["data"]} == {"fake-small", "fake-medium", "fake-large"}
    assert c.get("/health").json()["status"] == "ok"


def test_latency_model_ttft_grows_with_prompt_and_tier():
    from fake_provider import LATENCY
    s, m, l = (LATENCY[x] for x in ("fake-small", "fake-medium", "fake-large"))
    assert s["tpot"] < m["tpot"] < l["tpot"]
    assert s["ttft_base"] < m["ttft_base"] < l["ttft_base"]


def test_real_time_scale_actually_delays():
    import time
    cfg = Config(time_scale=0.05)
    c = TestClient(create_app(cfg))
    t0 = time.perf_counter()
    chat(c, n=100)
    dt = time.perf_counter() - t0
    assert dt > (0.25 + 99 * 0.012) * 0.05 * 0.6


def test_openai_sdk_compatible_chat_and_responses():
    c, _ = make()
    client = OpenAI(base_url="http://testserver/v1", api_key="x", http_client=c)
    r = client.chat.completions.create(model="fake-small", messages=MSG, extra_headers={"x-fake-output-tokens": "7"})
    assert r.usage.completion_tokens == 7
    r2 = client.responses.create(model="fake-small", input="Đơn AT1 ở đâu?", extra_headers={"x-fake-output-tokens": "6"})
    assert r2.usage.output_tokens == 6 and len(r2.output_text.split()) == 6


def test_openai_sdk_streaming_chat_and_responses():
    c, _ = make()
    client = OpenAI(base_url="http://testserver/v1", api_key="x", http_client=c)
    s = client.chat.completions.create(model="fake-small", messages=MSG, stream=True, extra_headers={"x-fake-output-tokens": "5"})
    assert len("".join(ch.choices[0].delta.content or "" for ch in s if ch.choices).split()) == 5
    events = list(client.responses.create(model="fake-small", input="x", stream=True, extra_headers={"x-fake-output-tokens": "4"}))
    deltas = [e.delta for e in events if e.type == "response.output_text.delta"]
    assert len("".join(deltas).split()) == 4
    assert events[-1].type == "response.completed" and events[-1].response.usage.output_tokens == 4


def test_capacity_429_when_over_limit():
    c, cfg = make(capacity=1)
    from fake_provider import create_app as _  # noqa
    app = c.app
    app.state.stats.inflight = 5
    assert chat(c).status_code == 429
