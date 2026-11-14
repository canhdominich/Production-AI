import statistics
import time

from openai import OpenAI

from _harness import provider
from common import percentile

SCALE = 0.1
N = 60


def run(client, calls):
    totals = []
    for i in range(N):
        t0 = time.perf_counter()
        for step in range(calls):
            client.chat.completions.create(model="fake-small", messages=[{"role": "user", "content": "tom tat khieu nai"}],
                                           extra_headers={"x-fake-request-id": f"u{i}-s{step}", "x-fake-output-tokens": "80"})
        totals.append((time.perf_counter() - t0) / SCALE)
    return totals


with provider(5610, seed=42, time_scale=SCALE, faults={"slow": 0.05}, slow_factor=5) as (url, cfg, app):
    client = OpenAI(base_url=url + "/v1", api_key="x")
    print("5% of provider calls are 5 times slower. Seconds per user request, scaled back:")
    for calls in (1, 4):
        t = run(client, calls)
        slow_users = sum(1 for x in t if x > 1.5 * statistics.median(t)) / N
        print(f"  {calls} model call(s) per request: p50 {statistics.median(t):5.2f}  p95 {percentile(t, 95):5.2f}  users with a slow request {slow_users:5.1%}")
    print("chance that at least one of 4 calls is slow:", f"{1 - 0.95 ** 4:.1%}")
