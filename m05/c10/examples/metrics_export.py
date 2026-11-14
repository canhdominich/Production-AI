from prometheus_client import CollectorRegistry, Counter, Gauge, generate_latest
from prometheus_client.parser import text_string_to_metric_families

from _kit import MONTH_START, SCHEMA, TenantRegistry, connect

registry = CollectorRegistry()
cost = Counter("ai_cost_usd", "Model spend in USD", ["tenant", "feature", "tier"], registry=registry)
tokens = Counter("ai_tokens", "Tokens processed", ["tenant", "feature", "direction"], registry=registry)
used = Gauge("ai_budget_used_ratio", "Month to date spend divided by monthly budget", ["tenant"], registry=registry)

budgets = {t.tenant_id: t.monthly_budget_usd for t in TenantRegistry().all()}
with connect() as conn:
    spend = {}
    for tenant, feature, tier, prompt, output, usd in conn.execute(
            f"SELECT tenant_id, feature, tier, sum(prompt_tokens), sum(output_tokens), sum(cost_usd) FROM {SCHEMA}.usage_events "
            f"WHERE ts >= %s AND ts < '2026-11-01' GROUP BY 1, 2, 3", (MONTH_START,)):
        cost.labels(tenant, feature, tier).inc(float(usd))
        tokens.labels(tenant, feature, "prompt").inc(int(prompt))
        tokens.labels(tenant, feature, "output").inc(int(output))
        spend[tenant] = spend.get(tenant, 0.0) + float(usd)
    for tenant, budget in budgets.items():
        used.labels(tenant).set(round(spend[tenant] / budget, 4))

    text = generate_latest(registry).decode()
    lines = [x for x in text.splitlines() if ('ai_cost_usd_total' in x and 'br-xom-vui' in x and not x.startswith('#')) or x.startswith("ai_budget_used_ratio")]
    print("exposition format (excerpt):")
    for x in ["# TYPE ai_cost_usd_total counter"] + lines:
        print(" ", x)
    families = list(text_string_to_metric_families(text))
    series = sum(len(f.samples) for f in families if not f.name.endswith("_created"))
    print(f"\nparsed back: {len(families)} metric families, {series} samples")

    def distinct(cols):
        return conn.execute(f"SELECT count(*) FROM (SELECT DISTINCT {cols} FROM {SCHEMA}.usage_events) s").fetchone()[0]

    print("\nhow many time series each label choice creates")
    for name, cols in [("tenant, feature, tier", "tenant_id, feature, tier"), ("add role", "tenant_id, feature, tier, role"),
                       ("add model and status", "tenant_id, feature, tier, role, model, status"), ("add request_id", "tenant_id, feature, tier, request_id")]:
        print(f"  {name:24} {distinct(cols):8d}")
