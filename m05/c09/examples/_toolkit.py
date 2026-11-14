import asyncio
import csv
import hashlib
import json
import math
import os
import random
import re
import subprocess
import sys
import time
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import numpy as np

PLATFORM = Path(__file__).resolve().parents[2] / "platform"
if str(PLATFORM) not in sys.path:
    sys.path.insert(0, str(PLATFORM))

from common import LAB_DIR, estimate_prompt_tokens, percentile
from gateway_core import Gateway
from workload import generate

PORT_PROVIDER = 5690
PORT_REDIS = 5692
SCALE = 0.25
PROVIDER_CFG = dict(capacity=24, knee=8, load_factor=1.5)
N_REQUESTS = 360
DURATION_S = 240.0
SLOTS = 10
SLO_TTFT_S = 3.0
SLO_TPOT_S = 0.06
CODE_RE = re.compile(r"\bat\d{6}\b", re.I)
NUM_RE = re.compile(r"\d+")


@contextmanager
def fake_provider(scale=SCALE, port=PORT_PROVIDER, **config):
    env = dict(os.environ, FAKE_TIME_SCALE=str(scale), FAKE_SEED="42")
    proc = subprocess.Popen([sys.executable, str(PLATFORM / "fake_provider.py"), "--port", str(port)], env=env, cwd=str(PLATFORM),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                if httpx.get(base + "/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.1)
        if config:
            httpx.post(base + "/admin/config", json=config, timeout=5).raise_for_status()
        yield base
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@contextmanager
def redis_server(port=PORT_REDIS):
    proc = subprocess.Popen(["redis-server", "--port", str(port), "--save", "", "--appendonly", "no", "--bind", "127.0.0.1"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        import redis
        r = redis.Redis(port=port, protocol=2)
        for _ in range(50):
            try:
                r.ping()
                break
            except redis.ConnectionError:
                time.sleep(0.1)
        yield port
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def provider_stats(base):
    return httpx.get(base + "/admin/stats", timeout=5).json()


def messages_truth():
    path = LAB_DIR / "m02" / "data" / "messages.csv"
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return {r["text"]: r for r in rows}


def truth_key(row):
    codes = sorted(c.upper() for c in CODE_RE.findall(row["text"]))
    return f"{row['template_id']}|{','.join(codes)}"


def strip_marks(text):
    s = unicodedata.normalize("NFD", text)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "D")
    return s.lower()


def surface_variant(text, rnd):
    kind = rnd.choice(["plain", "polite", "nopunct"])
    if kind == "plain":
        return strip_marks(text)
    if kind == "polite":
        return text.rstrip(".!? ") + " ạ"
    return text.rstrip(".!? ").lower()


@dataclass
class Job:
    req: object
    truth: str = ""
    cacheable: bool = False
    variant: bool = False
    text: str = ""


def make_traffic(n, seed=42, duration_s=160.0, variant_share=0.35, faq_share=0.5):
    truth = messages_truth()
    rnd = random.Random(seed + 1)
    faq = sorted((r for r in truth.values() if not CODE_RE.search(r['text'])), key=lambda r: r['message_id'])[:60]
    faq_weights = [1.0 / (i + 1) for i in range(len(faq))]
    jobs = []
    for r in generate(n, seed=seed, duration_s=duration_s):
        j = Job(r)
        last = r.messages[-1]["content"]
        first_turn = r.feature == "chat" and len(r.messages) == 2
        if first_turn and last in truth:
            if rnd.random() < faq_share:
                last = rnd.choices(faq, weights=faq_weights)[0]['text']
                r.messages[-1]['content'] = last
                r.prompt_tokens = estimate_prompt_tokens(r.messages)
            j.truth, j.cacheable = truth_key(truth[last]), True
            if rnd.random() < variant_share:
                r.messages[-1]["content"] = surface_variant(last, rnd)
                j.variant = True
        j.text = r.messages[-1]["content"]
        jobs.append(j)
    return jobs


def normalize(text):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def cache_key(tenant_id, model, messages, max_tokens=0, scope_tenant=True):
    body = {"m": model, "x": max_tokens, "msgs": [[m["role"], normalize(m["content"])] for m in messages]}
    if scope_tenant:
        body["t"] = tenant_id
    return "ec:" + hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:32]


class ExactCache:
    def __init__(self, redis_client, ttl_s=3600):
        self.r = redis_client
        self.ttl_s = ttl_s
        self.hits = self.misses = 0

    async def get(self, key):
        raw = await self.r.get(key)
        if raw is None:
            self.misses += 1
            return None
        self.hits += 1
        return json.loads(raw)

    async def put(self, key, value):
        await self.r.set(key, json.dumps(value, ensure_ascii=False), ex=self.ttl_s)


def entities(text):
    return sorted(NUM_RE.findall(text))


def cosine(a, b):
    return float(np.dot(a, b))


class SemanticCache:
    def __init__(self, threshold=0.92, guard=True):
        self.threshold = threshold
        self.guard = guard
        self.buckets = {}
        self.lookups = self.hits = 0

    def lookup(self, scope, vec, text):
        self.lookups += 1
        best, best_s = None, -1.0
        for e in self.buckets.get(scope, []):
            s = cosine(vec, e["vec"])
            if s > best_s:
                best, best_s = e, s
        if best is None or best_s < self.threshold:
            return None, best_s
        if self.guard and entities(text) != best["ents"]:
            return None, best_s
        self.hits += 1
        return best, best_s

    def add(self, scope, vec, text, value, truth=""):
        self.buckets.setdefault(scope, []).append({"vec": vec, "text": text, "ents": entities(text), "value": value, "truth": truth})


class Overloaded(Exception):
    def __init__(self, reason, retry_after_s=1.0):
        super().__init__(reason)
        self.reason = reason
        self.retry_after_s = retry_after_s


class Limiter:
    def __init__(self, max_concurrent, max_queue=None, max_wait_s=None):
        self.max_concurrent = max_concurrent
        self.max_queue = max_queue
        self.max_wait_s = max_wait_s
        self._sem = asyncio.Semaphore(max_concurrent)
        self.waiting = 0
        self.active = 0
        self.peak_waiting = 0

    async def __aenter__(self):
        if self._sem.locked():
            if self.max_queue is not None and self.waiting >= self.max_queue:
                raise Overloaded("queue_full")
            self.waiting += 1
            self.peak_waiting = max(self.peak_waiting, self.waiting)
            try:
                if self.max_wait_s is None:
                    await self._sem.acquire()
                else:
                    await asyncio.wait_for(self._sem.acquire(), self.max_wait_s)
            except asyncio.TimeoutError:
                raise Overloaded("wait_timeout") from None
            finally:
                self.waiting -= 1
        else:
            await self._sem.acquire()
        self.active += 1
        return self

    async def __aexit__(self, *exc):
        self.active -= 1
        self._sem.release()


@dataclass
class Outcome:
    request_id: str
    feature: str
    status: str
    ttft_s: float = 0.0
    total_s: float = 0.0
    out_tokens: int = 0
    cost_usd: float = 0.0
    wrong_hit: bool = False
    provider_call: bool = False
    note: str = ""
    tpot_s: float = 0.0


class AsyncGateway(Gateway):
    def __init__(self, base_url, scale=SCALE, limiter=None, feature_limiters=None, exact=None, semantic=None, embed=None, embed_cost_s=0.0, timeout_s=120.0, **kw):
        super().__init__([], **kw)
        self.base_url = base_url
        self.scale = scale
        self.limiter = limiter
        self.feature_limiters = feature_limiters or {}
        self.exact = exact
        self.semantic = semantic
        self.embed = embed
        self.embed_cost_s = embed_cost_s
        self.http = httpx.AsyncClient(timeout=timeout_s, limits=httpx.Limits(max_connections=2000, max_keepalive_connections=200))
        self.truth_of_exact = {}

    async def aclose(self):
        await self.http.aclose()

    async def _call_provider(self, job, t_start):
        r = job.req
        body = {"model": r.model, "messages": r.messages, "max_tokens": r.max_tokens, "stream": r.stream}
        if r.stream:
            body["stream_options"] = {"include_usage": True}
        first = last = None
        n_out = 0
        async with self.http.stream("POST", self.base_url + "/v1/chat/completions", json=body, headers=r.provider_headers()) as resp:
            if resp.status_code != 200:
                await resp.aread()
                return ("http_%d" % resp.status_code), None, None, 0
            if not r.stream:
                d = json.loads(await resp.aread())
                return "ok", time.perf_counter() - t_start, None, d["usage"]["completion_tokens"]
            async for line in resp.aiter_lines():
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                ev = json.loads(line[6:])
                if ev.get("usage"):
                    n_out = ev["usage"]["completion_tokens"]
                for c in ev.get("choices", []):
                    if c["delta"].get("content"):
                        last = time.perf_counter() - t_start
                        first = first if first is not None else last
        return "ok", first, last, n_out

    async def handle_job(self, job):
        r = job.req
        t0 = time.perf_counter()
        tenant = self.tenants.get(r.tenant_id)
        self.before_call(type("R", (), {"feature": r.feature, "role": r.role, "tier": r.tier})(), tenant)
        key = vec = None
        if self.exact is not None and job.cacheable:
            key = cache_key(r.tenant_id, r.model, r.messages, r.max_tokens)
            hit = await self.exact.get(key)
            if hit is not None:
                return Outcome(r.request_id, r.feature, "exact_hit", 0.0, time.perf_counter() - t0, hit["tokens"], wrong_hit=hit["truth"] != job.truth, note="exact")
        if self.semantic is not None and job.cacheable:
            await asyncio.sleep(self.embed_cost_s * self.scale)
            vec = self.embed(job.text)
            entry, _ = self.semantic.lookup((r.tenant_id, r.model), vec, job.text)
            if entry is not None:
                return Outcome(r.request_id, r.feature, "semantic_hit", 0.0, time.perf_counter() - t0, entry["value"]["tokens"], wrong_hit=entry["truth"] != job.truth, note="semantic")
        gate = self.feature_limiters.get(r.feature, self.limiter)
        try:
            if gate is None:
                status, ttft, last, n_out = await self._call_provider(job, t0)
            else:
                async with gate:
                    status, ttft, last, n_out = await self._call_provider(job, t0)
        except Overloaded as e:
            return Outcome(r.request_id, r.feature, "rejected", 0.0, time.perf_counter() - t0, note=e.reason)
        except httpx.HTTPError as e:
            return Outcome(r.request_id, r.feature, "error", 0.0, time.perf_counter() - t0, note=type(e).__name__, provider_call=True)
        total = time.perf_counter() - t0
        if status != "ok":
            return Outcome(r.request_id, r.feature, "error", 0.0, total, note=status, provider_call=True)
        cost = self.prices.cost(r.model, r.prompt_tokens, n_out)
        if key is not None:
            await self.exact.put(key, {"tokens": n_out, "truth": job.truth})
        if vec is not None:
            self.semantic.add((r.tenant_id, r.model), vec, job.text, {"tokens": n_out}, job.truth)
        tpot = (last - ttft) / (n_out - 1) if last is not None and n_out > 1 and last > ttft else 0.0
        return Outcome(r.request_id, r.feature, "ok", ttft if ttft is not None else total, total, n_out, cost, provider_call=True, tpot_s=tpot)


async def run_open_loop(gateway, jobs, scale=SCALE):
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    results = []

    async def fire(job):
        await asyncio.sleep(max(0.0, t0 + job.req.arrival_s * scale - loop.time()))
        sent = loop.time()
        late = sent - (t0 + job.req.arrival_s * scale)
        out = await gateway.handle_job(job)
        out.ttft_s += late
        out.total_s += late
        results.append(out)

    await asyncio.gather(*(fire(j) for j in jobs))
    return results, loop.time() - t0


async def run_closed_loop(gateway, jobs, workers):
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    queue = list(reversed(jobs))
    results = []

    async def worker():
        while queue:
            results.append(await gateway.handle_job(queue.pop()))

    await asyncio.gather(*(worker() for _ in range(workers)))
    return results, loop.time() - t0


def pct(values, p):
    return percentile(values, p) if values else float("nan")


def summarize(results, wall_s, scale=SCALE):
    k = 1.0 / scale
    done = [o for o in results if o.status in ("ok", "exact_hit", "semantic_hit")]
    stream = [o for o in done if o.feature != "weekly_report_agent"]
    ttft = [o.ttft_s * k for o in stream]
    good = [o for o in stream if o.ttft_s * k <= SLO_TTFT_S and o.tpot_s * k <= SLO_TPOT_S]
    served = [o for o in results if o.status in ("ok", "exact_hit", "semantic_hit")]
    n = len(results)
    hits = [o for o in results if o.status in ("exact_hit", "semantic_hit")]
    return dict(
        n=n, served=len(served), rejected=sum(o.status == "rejected" for o in results), errors=sum(o.status == "error" for o in results),
        hits=len(hits), wrong_hits=sum(o.wrong_hit for o in hits), provider_calls=sum(o.provider_call for o in results),
        ttft_p50=pct(ttft, 50), ttft_p95=pct(ttft, 95), ttft_p99=pct(ttft, 99),
        slo_ok=len(good) / max(1, sum(1 for o in results if o.feature != "weekly_report_agent")),
        tok_per_s=sum(o.out_tokens for o in served) / (wall_s * k) if wall_s else 0.0,
        goodput=sum(o.out_tokens for o in good) / (wall_s * k) if wall_s else 0.0,
        cost=sum(o.cost_usd for o in results), wall_real=wall_s * k,
    )


def load_embedder():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("intfloat/multilingual-e5-small", device="cpu")

    def embed_many(texts):
        return model.encode(["query: " + t for t in texts], normalize_embeddings=True, batch_size=32, show_progress_bar=False)

    return embed_many


def print_table(rows, extra=()):
    cols = ["served", "rejected", "errors", "ttft_p50", "ttft_p95", "slo_ok", "goodput"] + list(extra)
    head = f"{'config':26}" + "".join(f"{c:>10}" for c in cols)
    print(head)
    for name, s in rows:
        cells = []
        for c in cols:
            v = s[c]
            cells.append(f"{v:>10.1%}" if c == "slo_ok" else f"{v:>10.2f}" if isinstance(v, float) else f"{v:>10}")
        print(f"{name:26}" + "".join(cells))


EMBED_COST_S = 0.09


def embed_lookup(jobs, embed_many):
    texts = sorted({j.text for j in jobs if j.cacheable})
    vecs = embed_many(texts)
    table = dict(zip(texts, vecs))
    return lambda t: table[t]
