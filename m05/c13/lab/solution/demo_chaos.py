import json
import os
import subprocess
import sys
import time
from pathlib import Path

PLATFORM = os.environ.get("M05_PLATFORM", str(Path(__file__).resolve().parents[3] / "platform"))
sys.path.insert(0, PLATFORM)

import httpx

from gateway_core import ProviderClient
from reliability import AllProvidersFailed, CircuitBreaker, ResilientCaller

SCALE = 0.05
MESSAGES = [{"role": "user", "content": "Don AT000123 den chua?"}]


def start(port, seed, faults):
    env = dict(os.environ, FAKE_SEED=str(seed), FAKE_TIME_SCALE=str(SCALE), FAKE_FAULTS=json.dumps(faults))
    proc = subprocess.Popen([sys.executable, str(Path(PLATFORM) / "fake_provider.py"), "--port", str(port)], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=PLATFORM)
    for _ in range(200):
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health", timeout=0.5).status_code == 200:
                break
        except httpx.TransportError:
            time.sleep(0.05)
    httpx.post(f"http://127.0.0.1:{port}/admin/config", json={"retry_after_s": 2.0 * SCALE})
    return proc


def chat(client):
    def call(request, remaining):
        return client.complete("fake-small", MESSAGES, request_id=request, output_tokens=60, timeout_s=min(0.5, remaining))
    return call


print(f"{'fault on A':<22} {'answered':>9} {'via B':>6} {'avg attempts':>13}")
for i, (label, faults) in enumerate((("429 on 40% of calls", {"rate_limit": 0.4}), ("500 on every call", {"error_500": 1.0}), ("timeout on every call", {"timeout": 1.0}))):
    procs = [start(5895 + 2 * i, 42, faults), start(5896 + 2 * i, 43, {})]
    try:
        a = ProviderClient("a", f"http://127.0.0.1:{5895 + 2 * i}")
        b = ProviderClient("b", f"http://127.0.0.1:{5896 + 2 * i}")
        breakers = {"a": CircuitBreaker(8, 30.0 * SCALE), "b": CircuitBreaker(8, 30.0 * SCALE)}
        caller = ResilientCaller([("a", chat(a)), ("b", chat(b))], breakers, max_attempts=2, base=0.5 * SCALE, cap=8.0 * SCALE, deadline_s=30.0 * SCALE)
        done = via_b = attempts = 0
        for n in range(30):
            try:
                r = caller.call(f"drill-{i}-{n}")
                done, via_b, attempts = done + 1, via_b + r.fallback_used, attempts + r.attempts
            except AllProvidersFailed:
                pass
        print(f"{label:<22} {done:>7}/30 {via_b:>6} {attempts / max(1, done):>13.2f}")
    finally:
        for p in procs:
            p.terminate()
            p.wait(timeout=5)
