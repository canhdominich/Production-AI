import json
from collections import Counter, defaultdict

import _kit  # noqa: F401
from anhti_platform.base import DATA_DIR, PriceTable, TenantRegistry
from workload import generate

reg, prices = TenantRegistry(), PriceTable()
day = generate(2000, seed=42)
cost = defaultdict(float)
mix = defaultdict(Counter)
for r in day:
    cost[r.tenant_id] += prices.cost(r.model, r.prompt_tokens, r.output_tokens)
    mix[r.tenant_id][r.feature] += 1

print(f"{'tenant':20}{'req/day':>8}{'rpm cap':>8}{'budget':>8}{'30d cost':>9}{'used x1':>8}{'used x5':>8}")
for t in reg.all():
    month = cost[t.tenant_id] * 30
    print(f"{t.tenant_id:20}{sum(mix[t.tenant_id].values()):>8}{t.rate_limit_rpm:>8}{t.monthly_budget_usd:>8.0f}{month:>9.2f}"
          f"{month / t.monthly_budget_usd:>8.0%}{5 * month / t.monthly_budget_usd:>8.0%}")
print()
slo = 0.99
print("SLO 99% of requests without error over 30 days")
print("error budget: 1 failure allowed in every", round(1 / (1 - slo)), "requests, 100 per 10,000")
print("same budget as downtime:", round(30 * 24 * 60 * (1 - slo)), "minutes per 30 days")
print("prices illustrative:", json.loads((DATA_DIR / "prices.json").read_text())["illustrative"])
