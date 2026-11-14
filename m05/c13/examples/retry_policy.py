import httpx

from _kit import ProviderClient, ReliableGateway, ResilientCaller, chat_requests, drive, provider, summary

reqs = chat_requests(120)
MIX = {"rate_limit": 0.10, "error_500": 0.10, "timeout": 0.05}
print(f"{'scenario':<34} {'policy':<10} {'success':>8} {'p95 (s)':>8} {'calls to provider':>18}")
for i, (label, faults) in enumerate((("25% faults (429, 500, timeout)", MIX), ("provider down (100% 500)", {"error_500": 1.0}))):
    for policy, attempts in (("no retry", 1), ("3 attempts", 3)):
        with provider(5750 + i * 2 + (attempts > 1), faults=faults) as url:
            gw = ReliableGateway([ProviderClient("a", url)], max_attempts=attempts, breaker=False)
            s = summary(drive(gw, reqs))
            calls = httpx.get(url + "/admin/stats").json()["requests"]
        print(f"{label:<34} {policy:<10} {s['rate']:>7.1f}% {s['p95']:>8.1f} {calls:>11} ({calls / len(reqs):.2f}x)")

with provider(5760) as url:
    client = ProviderClient("a", url)
    seen = []

    def bad_model(request, remaining):
        seen.append(1)
        return client.complete("fake-xl", request.messages, request_id=request.request_id)

    try:
        ResilientCaller([("a", bad_model)], max_attempts=3, sleep=lambda s: None).call(reqs[0])
    except Exception as e:
        print(f"\nbad request (unknown model): {len(seen)} call, error kind = {e.kind}, status = {e.status_code}")
