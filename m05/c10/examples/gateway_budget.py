import httpx
import redis
from concurrent.futures import ThreadPoolExecutor

from _kit import PORT_REDIS, fake_provider, generate, redis_server
from _budget_lib import BudgetedGateway, BudgetExceeded, RedisBudget
from gateway_core import GatewayRequest, ProviderClient

TENANT = "br-ben-song"
DEMO_BUDGET = 0.20


def run(n, with_budget):
    with redis_server() as port, fake_provider() as base:
        r = redis.Redis(port=port, protocol=2, decode_responses=True)
        gw = BudgetedGateway([ProviderClient("fake", base)], RedisBudget(r, "2026-10"))
        tenant = gw.tenants.get(TENANT)
        tenant.monthly_budget_usd = DEMO_BUDGET if with_budget else 1e9
        reqs = [x for x in generate(n * 12, seed=11) if x.tenant_id == TENANT][:n]
        log = []

        def send(item):
            i, x = item
            q = GatewayRequest(x.tenant_id, x.feature, x.messages, x.tier, x.role, x.request_id, 0, x.output_tokens)
            try:
                resp = gw.handle(q)
                log.append((i, "ok", resp.record.model, resp.record.cost_usd))
            except BudgetExceeded:
                log.append((i, "blocked", "", 0.0))

        with ThreadPoolExecutor(1) as pool:
            list(pool.map(send, enumerate(reqs)))
        log.sort()
        return log, gw, dict(httpx.get(base + "/admin/stats").json(), counter=gw.budget.spent(TENANT), index={x.request_id: i for i, x in enumerate(reqs)})


free, _, _ = run(600, False)
log, gw, stats = run(600, True)
spent = sum(c for _, s, _, c in log)
blocked = [i for i, s, _, _ in log if s == "blocked"]
models = {}
for _, s, m, _ in log:
    if s == "ok":
        models[m] = models.get(m, 0) + 1
print(f"tenant {TENANT}, demo budget ${DEMO_BUDGET:.2f} (a month of the real budget is $60), 600 requests in arrival order")
print(f"  without a budget:  ${sum(c for _, _, _, c in free):.3f} spent")
print(f"  with a budget:     ${spent:.3f} spent, {len(log) - len(blocked)} served, {len(blocked)} blocked")
print(f"  first blocked request: number {blocked[0]} of {len(log)}; blocked after that: {len(blocked)}")
print(f"  downgrade began at request number {min(stats['index'][e[1]] for e in gw.events if e[0] == 'downgrade')}")
print(f"  downgraded to a cheaper tier: {sum(1 for e in gw.events if e[0] == 'downgrade')} requests")
print(f"  models used: {models}")
print(f"  provider completed {stats['completed']} calls; budget counter ${stats['counter']:.3f}")
