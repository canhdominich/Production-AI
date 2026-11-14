import time

import httpx

from _harness import provider
from common import load_json

SCALE = 0.2
PROXY_TIMEOUT_S = 60
prices = load_json("prices.json")["models"]["fake-large"]
body = {"model": "fake-large", "messages": [{"role": "user", "content": "Lap bao cao tuan cho chi nhanh Cau Go"}]}

with provider(5610, seed=42, time_scale=SCALE) as (url, cfg, app):
    t0 = time.perf_counter()
    try:
        httpx.post(url + "/v1/chat/completions", json=body, headers={"x-fake-output-tokens": "2200"}, timeout=PROXY_TIMEOUT_S * SCALE)
        print("report returned")
    except httpx.ReadTimeout:
        print(f"client gave up after {(time.perf_counter() - t0) / SCALE:.0f} s (proxy timeout {PROXY_TIMEOUT_S} s)")
    stats = httpx.get(url + "/admin/stats").json()
    print("provider output tokens right after the client left:", stats["output_tokens"], "inflight:", stats["inflight"])
    while httpx.get(url + "/admin/stats").json()["inflight"]:
        time.sleep(0.2)
    stats = httpx.get(url + "/admin/stats").json()
    cost = (stats["prompt_tokens"] * prices["input_per_mtok"] + stats["output_tokens"] * prices["output_per_mtok"]) / 1e6
    print("provider finished anyway:", stats["output_tokens"], "output tokens generated and billed, cost", f"{cost:.4f} USD")
    print("tokens the user received: 0")
