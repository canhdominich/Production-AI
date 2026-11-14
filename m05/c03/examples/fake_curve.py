import statistics
import time

import httpx

from _harness import provider, run_threads
from common import percentile

SCALE = 0.1
OUT = 60
SLO_TTFT, SLO_TPOT = 2.5, 0.03
body = {"model": "fake-medium", "messages": [{"role": "user", "content": "Don AT123456 den luc nao?"}], "stream": True}


def call(i):
    t0 = time.perf_counter()
    first = last = None
    n = 0
    with httpx.Client(timeout=60) as http:
        with http.stream("POST", URL + "/v1/chat/completions", json=body, headers={"x-fake-request-id": f"r{i}", "x-fake-output-tokens": str(OUT)}) as resp:
            for line in resp.iter_lines():
                if line.startswith("data: ") and '"content": "' in line and '"content": ""' not in line:
                    now = time.perf_counter()
                    first = first or now
                    last = now
                    n += 1
    return (first - t0) / SCALE, (last - first) / max(1, n - 1) / SCALE, n


print("conc  ttft p95  tpot p50   throughput  goodput  ok%%   (fake-medium, scaled back by 1/%.1f)" % SCALE)
with provider(5630, seed=42, time_scale=SCALE, knee=8, load_factor=1.0) as (URL, cfg, app):
    for c in (1, 4, 8, 16, 32, 64):
        t0 = time.perf_counter()
        res = run_threads(call, range(c * 3), workers=c)
        wall = (time.perf_counter() - t0) / SCALE
        ok = [r for r in res if r[0] <= SLO_TTFT and r[1] <= SLO_TPOT]
        tok = sum(r[2] for r in res)
        print(f"{c:>4}  {percentile([r[0] for r in res], 95):7.2f}  {statistics.median(r[1] for r in res)*1000:5.1f} ms  {tok/wall:8.1f} t/s  {sum(r[2] for r in ok)/wall:6.1f}  {100*len(ok)/len(res):4.0f}")
