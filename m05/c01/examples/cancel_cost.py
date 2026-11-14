import threading
import time

import httpx

from _harness import provider

SCALE = 0.1
N = 6
OUT = 600
TIMES = (0.9 + 0.0015 * 20 + (OUT - 1) * 0.035) * SCALE
CANCEL_AFTER = 0.3 * TIMES


def nonstream(url, i):
    try:
        httpx.post(url + "/v1/chat/completions", json={"model": "fake-large", "messages": [{"role": "user", "content": "bao cao"}]},
                   headers={"x-fake-output-tokens": str(OUT), "x-fake-request-id": f"n{i}"}, timeout=CANCEL_AFTER)
    except httpx.ReadTimeout:
        pass


def stream(url, i):
    t0 = time.perf_counter()
    with httpx.stream("POST", url + "/v1/chat/completions", json={"model": "fake-large", "messages": [{"role": "user", "content": "bao cao"}], "stream": True},
                      headers={"x-fake-output-tokens": str(OUT), "x-fake-request-id": f"s{i}"}, timeout=30) as r:
        for _ in r.iter_lines():
            if time.perf_counter() - t0 > CANCEL_AFTER:
                break


def settle(url):
    time.sleep(0.5)
    while httpx.get(url + "/admin/stats").json()["inflight"]:
        time.sleep(0.2)
    return httpx.get(url + "/admin/stats").json()


for name, fn in (("non-streaming call, client gives up at 30%", nonstream), ("streaming call, client closes at 30%", stream)):
    with provider(5610, seed=42, time_scale=SCALE, load_factor=0.0) as (url, cfg, app):
        threads = [threading.Thread(target=fn, args=(url, i)) for i in range(N)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        s = settle(url)
        print(f"{name:<46} billed output tokens: {s['output_tokens']:>5} of {N * OUT} asked ({s['output_tokens'] / (N * OUT):.0%})")
