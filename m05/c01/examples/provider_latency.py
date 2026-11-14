import statistics
import time

import httpx

from _harness import provider
from common import percentile
from workload import generate

SCALE = 0.1
chat = [r for r in generate(400, seed=42) if r.feature == "chat"][:25]

with provider(5610, seed=42, time_scale=SCALE) as (url, cfg, app):
    print("tier          n   ttft p50   latency p50   latency p95   latency max   (seconds, scaled back by 1/%.1f)" % SCALE)
    for model in ("fake-small", "fake-medium", "fake-large"):
        ttft, total = [], []
        with httpx.Client(timeout=30) as http:
            for r in chat:
                body = {"model": model, "messages": r.messages, "stream": True}
                t0 = time.perf_counter()
                first = None
                with http.stream("POST", url + "/v1/chat/completions", json=body, headers=r.provider_headers()) as resp:
                    for line in resp.iter_lines():
                        if first is None and line.startswith("data: ") and '"content": "' in line and '"content": ""' not in line:
                            first = time.perf_counter() - t0
                total.append((time.perf_counter() - t0) / SCALE)
                ttft.append(first / SCALE)
        print(f"{model:<12} {len(chat):>3}   {statistics.median(ttft):7.2f}   {statistics.median(total):11.2f}   {percentile(total, 95):11.2f}   {max(total):11.2f}")
