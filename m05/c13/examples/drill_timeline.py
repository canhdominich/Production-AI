import time

import httpx

from _kit import ProviderClient, ReliableGateway, SCALE, chat_requests, drive, provider, set_faults, summary

reqs = chat_requests(240)
phases = [("1 steady", {}, reqs[:80]), ("2 outage of A", {"error_500": 1.0}, reqs[80:160]), ("3 A healed", {}, reqs[160:240])]
with provider(5880) as url_a, provider(5881, seed=43) as url_b:
    gw = ReliableGateway([ProviderClient("provider-a", url_a, timeout_s=0.5), ProviderClient("provider-b", url_b, timeout_s=0.5)])
    t0 = time.monotonic()
    print(f"{'phase':<16} {'success':>8} {'p95 (s)':>8} {'calls to A':>11} {'breaker A at end':>17}")
    for label, faults, batch in phases:
        set_faults(url_a, faults)
        if label.startswith("3"):
            time.sleep(35 * SCALE)
        s = summary(drive(gw, batch))
        calls_a = httpx.get(url_a + "/admin/stats").json()["requests"]
        print(f"{label:<16} {s['rate']:>7.1f}% {s['p95']:>8.1f} {calls_a:>11} {gw.breakers['provider-a'].state:>17}")
    print("\nbreaker A transitions (seconds since the drill started, real-world scale):")
    for stamp, state in gw.breakers["provider-a"].transitions:
        print(f"  {state:<10} at {(stamp - t0) / SCALE:6.1f} s")
