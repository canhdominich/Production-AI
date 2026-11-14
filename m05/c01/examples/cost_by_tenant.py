from collections import defaultdict

from _harness import PLATFORM
from common import load_json
from workload import generate

prices = load_json("prices.json")["models"]
requests = generate(2000, seed=42)


def cost(r):
    p = prices[r.model]
    return (p["input_per_mtok"] * r.prompt_tokens + p["output_per_mtok"] * r.output_tokens) / 1_000_000


per_tenant = defaultdict(lambda: [0, 0.0])
for r in requests:
    per_tenant[r.tenant_id][0] += 1
    per_tenant[r.tenant_id][1] += cost(r)

print("tenant                requests   cost USD   per 1,000 requests")
for tenant, (n, c) in sorted(per_tenant.items(), key=lambda kv: -kv[1][1]):
    print(f"{tenant:<20} {n:>8}   {c:8.4f}   {c / n * 1000:18.3f}")

costs = sorted((cost(r) for r in requests), reverse=True)
top = costs[: len(costs) // 20]
print(f"top 5% most expensive requests ({len(top)}) hold {sum(top) / sum(costs):.1%} of the total cost")
