from collections import Counter

from _harness import PLATFORM
from common import percentile, load_json
from workload import generate

prices = load_json("prices.json")["models"]
requests = generate(2000, seed=42)

print("feature               n    prompt p50/p95    output p50/p95/p99   cost share")
total_cost = sum(prices[r.model]["input_per_mtok"] * r.prompt_tokens + prices[r.model]["output_per_mtok"] * r.output_tokens for r in requests)
for feature in ("chat", "knowledge_assistant", "weekly_report_agent"):
    rs = [r for r in requests if r.feature == feature]
    cost = sum(prices[r.model]["input_per_mtok"] * r.prompt_tokens + prices[r.model]["output_per_mtok"] * r.output_tokens for r in rs)
    p = [round(percentile([r.prompt_tokens for r in rs], q)) for q in (50, 95)]
    o = [round(percentile([r.output_tokens for r in rs], q)) for q in (50, 95, 99)]
    print(f"{feature:<20} {len(rs):>4}   {p[0]:>5} / {p[1]:<5}    {o[0]:>5} / {o[1]:>4} / {o[2]:<5}   {cost / total_cost:6.1%}")

by_out = sorted(requests, key=lambda r: r.output_tokens, reverse=True)
top = by_out[: len(by_out) // 20]
print("top 5% longest outputs hold", f"{sum(r.output_tokens for r in top) / sum(r.output_tokens for r in requests):.1%}", "of all output tokens")
print("requests per tenant:", dict(Counter(r.tenant_id for r in requests)))
