import httpx

from _kit import ProviderClient, ReliableGateway, chat_requests, drive, provider, summary

reqs = chat_requests(150)
MIX = {"rate_limit": 0.15, "error_500": 0.10, "timeout": 0.10}
print("provider A injects 35% faults (15% 429, 10% 500, 10% timeout); provider B is healthy; 150 chat requests")
print(f"{'setup':<30} {'success':>8} {'p95 (s)':>8} {'retried':>8} {'via B':>6} {'calls A':>8} {'calls B':>8}")
sample = None
for i, (label, attempts, use_b, br) in enumerate((("A only, no retry", 1, False, False), ("A with retry", 3, False, False),
                                                  ("A + retry + fallback to B", 3, True, False), ("same + circuit breaker", 3, True, True))):
    with provider(5770 + i * 2, faults=MIX) as url_a, provider(5771 + i * 2, seed=43) as url_b:
        providers = [ProviderClient("provider-a", url_a, timeout_s=0.5)] + ([ProviderClient("provider-b", url_b, timeout_s=0.5)] if use_b else [])
        gw = ReliableGateway(providers, max_attempts=attempts, breaker=br, per_try_s=10.0, deadline_s=30.0)
        s = summary(drive(gw, reqs))
        calls_a = httpx.get(url_a + "/admin/stats").json()["requests"]
        calls_b = httpx.get(url_b + "/admin/stats").json()["requests"]
        sample = gw.sink.records
    print(f"{label:<30} {s['rate']:>7.1f}% {s['p95']:>8.1f} {s['retried']:>8} {s['fallback']:>6} {calls_a:>8} {calls_b:>8}")

print("\nthree usage records of the last setup (fields added by the gateway):")
for r in [x for x in sample if x.fallback_used][:2] + [x for x in sample if x.attempts == 1][:1]:
    print(f"  {r.request_id}  provider={r.provider:<10} attempts={r.attempts} fallback_used={r.fallback_used!s:<5} status={r.status}")
