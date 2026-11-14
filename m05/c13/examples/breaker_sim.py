import random

from _kit import AllProvidersFailed, CircuitBreaker, Clock, ProviderFailure, ResilientCaller, percentile

OUTAGE = (60.0, 180.0)
REQUESTS, GAP_S, PER_TRY_S, SLO_S = 600, 0.5, 5.0, 8.0


def simulate(use_fallback, use_breaker):
    clock = Clock()
    calls_a = {"outage": 0, "all": 0}

    def provider_a(request, remaining):
        calls_a["all"] += 1
        if OUTAGE[0] <= clock.t < OUTAGE[1]:
            calls_a["outage"] += 1
            clock.t += min(PER_TRY_S, remaining)
            raise ProviderFailure("timeout")
        clock.t += 1.6
        return "answer"

    def provider_b(request, remaining):
        clock.t += 2.0
        return "answer"

    providers = [("a", provider_a)] + ([("b", provider_b)] if use_fallback else [])
    threshold = 5 if use_breaker else 10 ** 9
    breakers = {n: CircuitBreaker(threshold, 30.0, clock=clock) for n, _ in providers}
    caller = ResilientCaller(providers, breakers, max_attempts=2, base=0.5, deadline_s=30.0, clock=clock, sleep=clock.sleep, rnd=random.Random(3))
    ok, lat_all, lat_out = 0, [], []
    for i in range(REQUESTS):
        arrival = i * GAP_S
        clock.t = arrival
        try:
            caller.call(i)
            ok += 1
        except AllProvidersFailed:
            pass
        lat_all.append(clock.t - arrival)
        if OUTAGE[0] <= arrival < OUTAGE[1]:
            lat_out.append(clock.t - arrival)
    return ok, calls_a, lat_all, lat_out, breakers["a"].transitions


print(f"provider A is down from {OUTAGE[0]:.0f} s to {OUTAGE[1]:.0f} s; {REQUESTS} requests, one every {GAP_S} s; per-try timeout {PER_TRY_S:.0f} s")
print(f"{'setup':<30} {'success':>8} {'calls to A in outage':>21} {'mean latency in outage':>23} {'over ' + str(int(SLO_S)) + ' s':>8}")
for label, fb, br in (("retry only", False, False), ("retry + fallback", True, False), ("retry + fallback + breaker", True, True)):
    ok, calls_a, lat_all, lat_out, trans = simulate(fb, br)
    slow = sum(1 for x in lat_all if x > SLO_S)
    print(f"{label:<30} {100 * ok / REQUESTS:>7.1f}% {calls_a['outage']:>21} {sum(lat_out) / len(lat_out):>21.1f} s {slow:>8}")
print("\nbreaker of A, state changes (seconds on the virtual clock):")
print("  " + ", ".join(f"{t:.0f}s {s}" for t, s in trans))
