from _kit import ProviderClient, ReliableGateway, chat_requests, drive, provider, set_faults, summary

reqs = chat_requests(100)
STEADY = {"success_min": 99.0, "p95_max_s": 15.0}
EXPERIMENTS = [
    ("A: 30% rate limit (429)", {"rate_limit": 0.30}, {}),
    ("A: total outage (500)", {"error_500": 1.0}, {}),
    ("A: hangs on every call", {"timeout": 1.0}, {}),
    ("A: hangs, per-try timeout 4 s, 2 attempts", {"timeout": 1.0}, {"per_try_s": 4.0, "max_attempts": 2}),
    ("A and B: 40% faults each", {"error_500": 0.25, "timeout": 0.15}, {"both": True}),
    ("A and B: 40% faults, canned reply as last step", {"error_500": 0.25, "timeout": 0.15}, {"both": True, "degrade": True}),
]


def verdict(s):
    return "pass" if s["rate"] >= STEADY["success_min"] and s["p95"] <= STEADY["p95_max_s"] else "FAIL"


print(f"steady state: success at least {STEADY['success_min']:.0f}% and p95 at most {STEADY['p95_max_s']:.0f} s; 100 chat requests per experiment")
print(f"{'experiment':<48} {'replied':>8} {'p95 (s)':>8} {'via B':>6} {'canned':>7} {'bad':>4}  verdict")
for i, (label, faults, opts) in enumerate(EXPERIMENTS):
    both = opts.pop("both", False)
    with provider(5790 + i * 2, faults=faults) as url_a, provider(5791 + i * 2, seed=43, faults=faults if both else None) as url_b:
        gw = ReliableGateway([ProviderClient("provider-a", url_a, timeout_s=0.5), ProviderClient("provider-b", url_b, timeout_s=0.5)], **opts)
        s = summary(drive(gw, reqs))
    print(f"{label:<48} {s['rate']:>7.1f}% {s['p95']:>8.1f} {s['fallback']:>6} {s['degraded']:>7} {s['n'] - s['ok']:>4}  {verdict(s)}")
