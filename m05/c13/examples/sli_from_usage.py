from _kit import ProviderClient, ReliableGateway, SCALE, chat_requests, drive, provider
from reliability import compute_slis

TARGETS = {"availability": 0.99, "latency": 0.95, "quality": 0.95}
LATENCY_LIMIT_MS = 4000
reqs = chat_requests(200)
for i, r in enumerate(reqs):
    if i % 12 == 0:
        r.max_tokens = 60
MIX = {"error_500": 0.04, "timeout": 0.03, "slow": 0.10}


def records_of(gw):
    rows = []
    for rec in gw.sink.records:
        rows.append({"status": "ok" if rec.status == "ok" else rec.error_kind, "latency_ms": rec.latency_ms / SCALE,
                     "finish_reason": gw.finishes.get(rec.request_id, "stop")})
    return rows


print(f"200 chat requests; provider A injects {sum(MIX.values()):.0%} faults (4% 500, 3% timeout, 10% slow); 1 request in 12 asks for too few tokens")
for i, (label, attempts, with_b) in enumerate((("A only, no retry", 1, False), ("A + retry + fallback to B", 3, True))):
    with provider(5780 + i * 2, faults=MIX) as url_a, provider(5781 + i * 2, seed=43) as url_b:
        providers = [ProviderClient("provider-a", url_a, timeout_s=0.5)] + ([ProviderClient("provider-b", url_b, timeout_s=0.5)] if with_b else [])
        gw = ReliableGateway(providers, max_attempts=attempts, breaker=False, deadline_s=30.0)
        drive(gw, reqs)
        slis = compute_slis(records_of(gw), LATENCY_LIMIT_MS)
    print(f"\n{label}")
    for name, value in slis.items():
        print(f"  {name:<13} {value:7.1%}   target {TARGETS[name]:.0%}   {'met' if value >= TARGETS[name] else 'missed'}")
