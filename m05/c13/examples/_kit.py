import contextlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLATFORM = str(HERE.parents[1] / "platform")
SOLUTION = str(HERE.parent / "lab" / "solution")
for p in (PLATFORM, SOLUTION):
    if p not in sys.path:
        sys.path.insert(0, p)

import httpx

from common import percentile
from gateway_core import Gateway, GatewayRequest, GatewayResponse, ProviderClient, ProviderError
from reliability import AllProvidersFailed, CircuitBreaker, ProviderFailure, ResilientCaller, backoff_delay, retry_wait
from workload import generate

SCALE = 0.05


CANNED_REPLY = "Xin loi, he thong dang ban. Ban vui long thu lai sau it phut."


class ProviderUnavailable(Exception):
    status = 503


@contextlib.contextmanager
def provider(port, seed=42, time_scale=SCALE, faults=None, **cfg):
    env = dict(os.environ, FAKE_SEED=str(seed), FAKE_TIME_SCALE=str(time_scale))
    if faults:
        env["FAKE_FAULTS"] = json.dumps(faults)
    proc = subprocess.Popen([sys.executable, str(Path(PLATFORM) / "fake_provider.py"), "--port", str(port)], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=PLATFORM)
    url = f"http://127.0.0.1:{port}"
    for _ in range(200):
        try:
            if httpx.get(f"{url}/health", timeout=0.5).status_code == 200:
                break
        except httpx.TransportError:
            time.sleep(0.05)
    cfg.setdefault("retry_after_s", 2.0 * time_scale)
    if cfg:
        httpx.post(f"{url}/admin/config", json=cfg)
    try:
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def set_faults(url, faults):
    httpx.post(url + "/admin/config", json={"faults": faults})
    httpx.post(url + "/admin/reset")


def chat_requests(n, cap=100, seed=42):
    reqs = [r for r in generate(n * 3, seed=seed) if r.feature == "chat"][:n]
    return [GatewayRequest(r.tenant_id, r.feature, r.messages, tier="small", role=r.role, request_id=r.request_id,
                           output_tokens=min(r.output_tokens, cap)) for r in reqs]


class ReliableGateway(Gateway):
    """Gateway with retry, per-try timeout, deadline, fallback and one circuit breaker per provider.
    All durations are given in real-world seconds and multiplied by the time scale of the fake provider."""

    def __init__(self, providers, per_try_s=10.0, deadline_s=30.0, max_attempts=3, base_s=0.5, cap_s=8.0,
                 breaker=True, scale=SCALE, failure_threshold=5, cooldown_s=30.0, degrade=False, **kw):
        super().__init__(providers, **kw)
        self.scale = scale
        self.degrade = degrade
        self.per_try = per_try_s * scale
        breakers = {p.name: CircuitBreaker(failure_threshold, cooldown_s * scale) for p in providers} if breaker else {p.name: CircuitBreaker(10 ** 9) for p in providers}
        self.callers = {}
        self._args = dict(breakers=breakers, max_attempts=max_attempts, base=base_s * scale, cap=cap_s * scale, deadline_s=deadline_s * scale)
        self.breakers = breakers
        self.lock = threading.Lock()
        self.finishes = {}

    def handle(self, req):
        tenant = self.tenants.get(req.tenant_id)
        self.before_call(req, tenant)
        model = self.prices.model_for(req.tier)
        started = time.perf_counter()

        def make(prov):
            def call(r, remaining):
                return prov.complete(model, r.messages, r.max_tokens or None, r.request_id, r.output_tokens or None,
                                     timeout_s=min(self.per_try, remaining))
            return call

        caller = ResilientCaller([(p.name, make(p)) for p in self.providers], **self._args)
        by_name = {p.name: p for p in self.providers}
        try:
            res = caller.call(req)
        except (AllProvidersFailed, ProviderError) as e:
            last = e.attempts[-1][1] if isinstance(e, AllProvidersFailed) and e.attempts else getattr(e, "kind", "error")
            err = ProviderError(last if last != "circuit_open" else "server_error")
            rec = self.record_failure(req, self.providers[-1], model, err, started, attempts=len(getattr(e, "attempts", [])) or 1)
            if self.degrade:
                rec.status = "degraded"
                return GatewayResponse(req.request_id, CANNED_REPLY, rec)
            raise ProviderUnavailable(str(e)) from None
        self.finishes[req.request_id] = res.value.finish_reason
        return self.finish(req, by_name[res.provider], model, res.value, started, attempts=res.attempts, fallback_used=res.fallback_used)


def drive(gw, reqs, workers=6):
    out, lock, it = [], threading.Lock(), iter(reqs)

    def loop():
        while True:
            with lock:
                r = next(it, None)
            if r is None:
                return
            t0 = time.perf_counter()
            try:
                resp = gw.handle(r)
                row = dict(ok=True, secs=(time.perf_counter() - t0) / gw.scale, attempts=resp.record.attempts, fallback=resp.record.fallback_used, kind="", degraded=resp.record.status == "degraded")
            except Exception as e:
                row = dict(ok=False, secs=(time.perf_counter() - t0) / gw.scale, attempts=0, fallback=False, kind=type(e).__name__, degraded=False)
            with lock:
                out.append(row)

    threads = [threading.Thread(target=loop) for _ in range(workers)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return out


def summary(rows):
    ok = [r for r in rows if r["ok"]]
    return dict(n=len(rows), ok=len(ok), rate=100 * len(ok) / len(rows), p50=percentile([r["secs"] for r in ok], 50) if ok else 0.0,
                p95=percentile([r["secs"] for r in ok], 95) if ok else 0.0, fallback=sum(r["fallback"] for r in ok), degraded=sum(r["degraded"] for r in ok),
                retried=sum(1 for r in ok if r["attempts"] > 1), calls=sum(r["attempts"] for r in ok))


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s
