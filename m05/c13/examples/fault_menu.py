import time

from _kit import ProviderClient, ProviderError, SCALE, chat_requests, provider

req = chat_requests(1)[0]
PER_TRY_S = 10.0
cases = [("none", {}), ("rate_limit", {"rate_limit": 1.0}), ("error_500", {"error_500": 1.0}), ("slow", {"slow": 1.0}), ("timeout", {"timeout": 1.0})]
print(f"{'injected fault':<12} {'client sees':<22} {'status':<7} {'retry-after':<12} seconds waited (real-world scale)")
for i, (name, faults) in enumerate(cases):
    with provider(5740 + i, faults=faults, retry_after_s=2.0) as url:
        client = ProviderClient("a", url, timeout_s=PER_TRY_S * SCALE)
        t0 = time.perf_counter()
        try:
            r = client.complete("fake-small", req.messages, request_id=req.request_id, output_tokens=100)
            seen, status, hint = "answer, finish=" + r.finish_reason, 200, "-"
        except ProviderError as e:
            seen, status, hint = e.kind, e.status_code or "-", e.retry_after or "-"
        print(f"{name:<12} {seen:<22} {status!s:<7} {hint!s:<12} {(time.perf_counter() - t0) / SCALE:5.1f}")
