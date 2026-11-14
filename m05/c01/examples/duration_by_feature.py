from _harness import PLATFORM
from common import percentile
from fake_provider import LATENCY
from workload import generate

PROXY_TIMEOUT_S = 60
requests = generate(3000, seed=42)


def expected_seconds(r):
    lat = LATENCY[r.model]
    ttft = lat["ttft_base"] + lat["ttft_per_token"] * r.prompt_tokens
    return ttft, ttft + (r.output_tokens - 1) * lat["tpot"]


print("feature                 n   ttft p50   total p50   total p95   total p99   over 10 s   over 60 s")
for feature in ("chat", "knowledge_assistant", "weekly_report_agent"):
    rs = [r for r in requests if r.feature == feature]
    ttft = [expected_seconds(r)[0] for r in rs]
    total = [expected_seconds(r)[1] for r in rs]
    over10 = sum(t > 10 for t in total) / len(total)
    over60 = sum(t > PROXY_TIMEOUT_S for t in total) / len(total)
    print(f"{feature:<20} {len(rs):>5}   {percentile(ttft, 50):7.2f}   {percentile(total, 50):9.1f}   {percentile(total, 95):9.1f}   {percentile(total, 99):9.1f}   {over10:8.1%}   {over60:8.1%}")
