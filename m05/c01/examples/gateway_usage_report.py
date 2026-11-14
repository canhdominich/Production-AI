import threading
import time
from collections import Counter, defaultdict

from _harness import provider
from _gateway_ext import BudgetExceeded, GatewayV1, TenantRateLimited
from gateway_core import GatewayRequest, ProviderClient
from workload import generate

SCALE = 0.02
reqs = generate(400, seed=42)

with provider(5610, seed=42, time_scale=SCALE) as (url, _, _):
    gw = GatewayV1([ProviderClient("provider-a", url)], max_concurrency=16, time_scale=SCALE)
    gw.tenants.get("br-ben-song").monthly_budget_usd = 0.02
    refused = Counter()
    lock, it = threading.Lock(), iter(reqs)

    def worker():
        while True:
            with lock:
                r = next(it, None)
            if r is None:
                return
            try:
                gw.handle(GatewayRequest(r.tenant_id, r.feature, r.messages, tier=r.tier, role=r.role, request_id=r.request_id, output_tokens=r.output_tokens))
            except (BudgetExceeded, TenantRateLimited) as e:
                refused[(r.tenant_id, type(e).__name__)] += 1

    threads = [threading.Thread(target=worker) for _ in range(16)]
    [t.start() for t in threads]
    [t.join() for t in threads]

rows = gw.sink.records
print("tenant                 calls  out tokens   cost USD   of budget   refused")
for t in gw.tenants.all():
    mine = [x for x in rows if x.tenant_id == t.tenant_id]
    cost = sum(x.cost_usd for x in mine)
    bad = ", ".join(f"{k[1]} x{v}" for k, v in refused.items() if k[0] == t.tenant_id) or "-"
    print(f"{t.tenant_id:<20} {len(mine):>6} {sum(x.output_tokens for x in mine):>11} {cost:>10.4f} {cost / t.monthly_budget_usd:>10.1%}   {bad}")
print("\nfeature                  share of calls   share of cost")
total = sum(x.cost_usd for x in rows)
for f in ("chat", "knowledge_assistant", "weekly_report_agent"):
    mine = [x for x in rows if x.feature == f]
    print(f"{f:<22} {len(mine) / len(rows):>13.1%} {sum(x.cost_usd for x in mine) / total:>15.1%}")
