import statistics

import _paths  # noqa: F401
from common import load_json
from workload import generate

requests = generate(2000, seed=42)
prices = load_json("prices.json")["models"]

print("feature               n   avg_in  avg_out")
for feature in ("chat", "knowledge_assistant", "weekly_report_agent"):
    rs = [r for r in requests if r.feature == feature]
    print(f"{feature:<20} {len(rs):>4} {statistics.mean(r.prompt_tokens for r in rs):8.0f} {statistics.mean(r.output_tokens for r in rs):8.0f}")

avg_in = statistics.mean(r.prompt_tokens for r in requests)
avg_out = statistics.mean(r.output_tokens for r in requests)
print(f"all                  {len(requests):>4} {avg_in:8.0f} {avg_out:8.0f}")

print("\nAPI cost per 1,000 requests at the mixed average (illustrative prices)")
for model, p in prices.items():
    per_request = (avg_in * p["input_per_mtok"] + avg_out * p["output_per_mtok"]) / 1_000_000
    print(f"{model:<12} {per_request * 1000:8.3f} USD per 1,000 requests")
