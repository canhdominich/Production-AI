import statistics
import threading
import time
from collections import Counter

import httpx

from _harness import provider
from _gateway_ext import GatewayV1, ProviderUnavailable
from common import percentile
from gateway_core import GatewayRequest, ProviderClient
from workload import generate

SCALE = 0.02
reqs = [r for r in generate(600, seed=42) if r.feature != "weekly_report_agent"][:150]


def run(call):
    results, lock, it = [], threading.Lock(), iter(reqs)

    def worker():
        while True:
            with lock:
                r = next(it, None)
            if r is None:
                return
            t0 = time.perf_counter()
            try:
                call(r)
                results.append(("ok", (time.perf_counter() - t0) / SCALE))
            except Exception as e:
                results.append((type(e).__name__, (time.perf_counter() - t0) / SCALE))

    threads = [threading.Thread(target=worker) for _ in range(12)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return results


with provider(5610, seed=42, time_scale=SCALE, faults={"error_500": 0.4}) as (url_a, _, _), provider(5611, seed=43, time_scale=SCALE) as (url_b, _, _):
    direct = ProviderClient("provider-a", url_a)
    res = run(lambda r: direct.complete(r.model, r.messages, request_id=r.request_id, output_tokens=min(r.output_tokens, 300)))
    ok = [t for s, t in res if s == "ok"]
    print(f"direct to provider A (40% errors) : success {len(ok)}/{len(res)}  p95 latency {percentile(ok, 95):5.1f} s")
    httpx.post(url_a + "/admin/reset")
    gw = GatewayV1([ProviderClient("provider-a", url_a), ProviderClient("provider-b", url_b)], max_concurrency=12, time_scale=SCALE)
    for t in gw.tenants.all():
        gw.buckets[t.tenant_id].burst, gw.buckets[t.tenant_id].tokens = 1000, 1000
    res = run(lambda r: gw.handle(GatewayRequest(r.tenant_id, r.feature, r.messages, tier=r.tier, role=r.role, request_id=r.request_id, output_tokens=min(r.output_tokens, 300))))
    ok = [t for s, t in res if s == "ok"]
    print(f"through gateway, A then B         : success {len(ok)}/{len(res)}  p95 latency {percentile(ok, 95):5.1f} s")
    rows = gw.sink.records
    good = [x for x in rows if x.status == "ok"]
    print("  usage rows:", Counter(x.status for x in rows))
    print("  answered by:", dict(Counter(x.provider for x in good)), "| fallback_used:", sum(x.fallback_used for x in good), "| attempts 2 or more:", sum(x.attempts > 1 for x in good))
    print(f"  cost recorded: {sum(x.cost_usd for x in good):.4f} USD, cost of the failed attempts: {sum(x.cost_usd for x in rows if x.status != 'ok'):.4f} USD")
