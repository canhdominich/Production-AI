import time

import httpx

from _harness import provider
from workload import generate

SCALE = 0.1
req = next(r for r in generate(500, seed=42) if r.feature == "knowledge_assistant")
cases = {"chat reply (medium, 200 tokens)": ("fake-medium", 200), "weekly report (large, 1500 tokens)": ("fake-large", 1500)}

with provider(5610, seed=42, time_scale=SCALE) as (url, cfg, app):
    print(f"{'case':<36}{'mode':<11}{'first byte':>11}{'complete':>10}   (seconds, scaled back by 1/{SCALE})")
    with httpx.Client(timeout=60) as http:
        for name, (model, n_out) in cases.items():
            headers = {"x-fake-output-tokens": str(n_out), "x-fake-request-id": name}
            body = {"model": model, "messages": req.messages}
            http.post(url + "/admin/reset")
            t0 = time.perf_counter()
            http.post(url + "/v1/chat/completions", json=body, headers=headers)
            wait = (time.perf_counter() - t0) / SCALE
            print(f"{name:<36}{'sync':<11}{wait:>11.1f}{wait:>10.1f}")
            http.post(url + "/admin/reset")
            t0 = time.perf_counter()
            first = None
            with http.stream("POST", url + "/v1/chat/completions", json={**body, "stream": True}, headers=headers) as resp:
                for line in resp.iter_lines():
                    if first is None and line.startswith("data: ") and '"content": ""' not in line:
                        first = (time.perf_counter() - t0) / SCALE
            print(f"{name:<36}{'streaming':<11}{first:>11.1f}{(time.perf_counter() - t0) / SCALE:>10.1f}")
