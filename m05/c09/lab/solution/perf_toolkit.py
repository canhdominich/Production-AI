import asyncio
import hashlib
import json
import math
import re
import unicodedata


def percentile(values, p):
    xs = sorted(values)
    if not xs:
        raise ValueError("empty list")
    k = (len(xs) - 1) * p / 100
    lo, hi = math.floor(k), math.ceil(k)
    return float(xs[lo]) if lo == hi else xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def summarize(outcomes):
    n = len(outcomes)
    served = [o for o in outcomes if o["status"] in ("ok", "hit")]
    ttft = [o["ttft_s"] for o in served]
    return {
        "n": n,
        "served": len(served),
        "reject_rate": sum(o["status"] == "rejected" for o in outcomes) / n if n else 0.0,
        "error_rate": sum(o["status"] == "error" for o in outcomes) / n if n else 0.0,
        "ttft_p50": percentile(ttft, 50) if ttft else 0.0,
        "ttft_p95": percentile(ttft, 95) if ttft else 0.0,
    }


def normalize(text):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def cache_key(tenant_id, model, messages):
    body = {"t": tenant_id, "m": model, "msgs": [[m["role"], normalize(m["content"])] for m in messages]}
    return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


class TTLCache:
    def __init__(self, ttl_s, clock):
        self.ttl_s = ttl_s
        self.clock = clock
        self.data = {}
        self.hits = 0
        self.misses = 0

    def get(self, key):
        item = self.data.get(key)
        if item is None or self.clock() >= item[0]:
            self.data.pop(key, None)
            self.misses += 1
            return None
        self.hits += 1
        return item[1]

    def put(self, key, value):
        self.data[key] = (self.clock() + self.ttl_s, value)


def numbers_of(text):
    return sorted(re.findall(r"\d+", text))


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class SemanticCache:
    def __init__(self, threshold, guard=True):
        self.threshold = threshold
        self.guard = guard
        self.entries = {}

    def add(self, scope, vec, text, value):
        self.entries.setdefault(scope, []).append((vec, text, value))

    def lookup(self, scope, vec, text):
        best, best_s = None, -1.0
        for v, t, value in self.entries.get(scope, []):
            s = cosine(vec, v)
            if s > best_s:
                best, best_s = (t, value), s
        if best is None or best_s < self.threshold:
            return None
        if self.guard and numbers_of(text) != numbers_of(best[0]):
            return None
        return best[1]


def wrong_hit_rate(results):
    hits = [r for r in results if r["hit"]]
    if not hits:
        return 0.0
    return sum(not r["correct"] for r in hits) / len(hits)


class Overloaded(Exception):
    pass


class Limiter:
    def __init__(self, max_concurrent, max_queue):
        self.max_concurrent = max_concurrent
        self.max_queue = max_queue
        self.sem = asyncio.Semaphore(max_concurrent)
        self.waiting = 0

    async def __aenter__(self):
        if self.sem.locked():
            if self.waiting >= self.max_queue:
                raise Overloaded("queue_full")
            self.waiting += 1
            try:
                await self.sem.acquire()
            finally:
                self.waiting -= 1
        else:
            await self.sem.acquire()
        return self

    async def __aexit__(self, *exc):
        self.sem.release()
