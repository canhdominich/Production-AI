from gateway_core import Gateway, GatewayError
from common import TIERS

SOFT_PCT = 80
HARD_PCT = 100
MIN_TIER = {"chat": "small", "knowledge_assistant": "medium", "weekly_report_agent": "large"}
EXPECTED_OUTPUT = {"chat": 120, "knowledge_assistant": 240, "weekly_report_agent": 1400}

RESERVE_LUA = """
local spent = tonumber(redis.call('GET', KEYS[1]) or '0')
local est = tonumber(ARGV[1])
if spent + est > tonumber(ARGV[2]) then
  return {0, tostring(spent)}
end
return {1, redis.call('INCRBYFLOAT', KEYS[1], ARGV[1])}
"""


class BudgetExceeded(GatewayError):
    status = 429


def budget_state(spent, budget, soft_pct=SOFT_PCT, hard_pct=HARD_PCT):
    ratio = spent / budget * 100
    return "hard" if ratio >= hard_pct else "soft" if ratio >= soft_pct else "ok"


def downgrade(tier, feature):
    floor = TIERS.index(MIN_TIER[feature])
    return TIERS[max(floor, TIERS.index(tier) - 1)]


class RedisBudget:
    def __init__(self, client, month):
        self.r = client
        self.month = month
        self._reserve = client.register_script(RESERVE_LUA)

    def key(self, tenant_id):
        return f"budget:{self.month}:{tenant_id}"

    def spent(self, tenant_id):
        return float(self.r.get(self.key(tenant_id)) or 0)

    def reserve(self, tenant_id, estimate, limit):
        ok, spent = self._reserve(keys=[self.key(tenant_id)], args=[estimate, limit])
        return bool(ok), float(spent)

    def settle(self, tenant_id, delta):
        self.r.incrbyfloat(self.key(tenant_id), delta)

    def warm_from_postgres(self, conn, schema, month_start, month_end):
        rows = conn.execute(f"SELECT tenant_id, sum(cost_usd) FROM {schema}.usage_events WHERE ts >= %s AND ts < %s GROUP BY 1", (month_start, month_end)).fetchall()
        for tenant_id, total in rows:
            self.r.set(self.key(tenant_id), float(total), nx=True)
        return len(rows)


class BudgetedGateway(Gateway):
    def __init__(self, providers, budget, **kw):
        super().__init__(providers, **kw)
        self.budget = budget
        self.events = []

    def estimate(self, req):
        from common import estimate_prompt_tokens
        model = self.prices.model_for(req.tier)
        return self.prices.cost(model, estimate_prompt_tokens(req.messages), EXPECTED_OUTPUT[req.feature])

    def before_call(self, req, tenant):
        super().before_call(req, tenant)
        limit = tenant.monthly_budget_usd
        state = budget_state(self.budget.spent(tenant.tenant_id), limit)
        if state == "soft":
            new = downgrade(req.tier, req.feature)
            if new != req.tier:
                self.events.append(("downgrade", req.request_id))
            req.tier = new
        est = self.estimate(req)
        ok, _ = self.budget.reserve(tenant.tenant_id, est, limit)
        if not ok:
            self.events.append(("blocked", req.request_id))
            raise BudgetExceeded(f"tenant {tenant.tenant_id} reached its monthly budget of ${limit:.2f}")
        req.reserved = est

    def finish(self, req, provider, model, result, started, **extra):
        resp = super().finish(req, provider, model, result, started, **extra)
        self.budget.settle(req.tenant_id, resp.record.cost_usd - req.reserved)
        return resp

    def on_error(self, req, tenant, provider, error, started):
        self.budget.settle(req.tenant_id, -req.reserved)
        raise error
