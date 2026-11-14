import psycopg

from _harness import provider, run_threads
from _gateway_ext import GatewayV1
from gateway_core import GatewayRequest, ProviderClient
from workload import generate

SCALE = 0.02
reqs = [r for r in generate(300, seed=42) if r.feature != "weekly_report_agent"][:120]

with provider(5610, seed=42, time_scale=SCALE) as (url, _, _):
    gw = GatewayV1([ProviderClient("provider-a", url)], max_concurrency=12, time_scale=SCALE)
    for t in gw.tenants.all():
        gw.buckets[t.tenant_id].burst = gw.buckets[t.tenant_id].tokens = 1000
    run_threads(lambda r: gw.handle(GatewayRequest(r.tenant_id, r.feature, r.messages, tier=r.tier, role=r.role, request_id=r.request_id, output_tokens=r.output_tokens)), reqs)

COLUMNS = "request_id, tenant_id, feature, model, provider, status, prompt_tokens, output_tokens, cost_usd, latency_ms"
with psycopg.connect("postgresql://anhti:anhti@localhost:55432/anhti", autocommit=True) as conn:
    conn.execute("create schema if not exists m05_c01")
    conn.execute("create table m05_c01.usage_events (request_id text primary key, tenant_id text, feature text, model text, provider text, status text, "
                 "prompt_tokens int, output_tokens int, cost_usd double precision, latency_ms double precision)")
    with conn.cursor() as cur:
        cur.executemany(f"insert into m05_c01.usage_events ({COLUMNS}) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        [tuple(getattr(x, c.strip()) for c in COLUMNS.split(",")) for x in gw.sink.records])
    print("rows written:", conn.execute("select count(*) from m05_c01.usage_events").fetchone()[0])
    rows = conn.execute("select tenant_id, feature, count(*), sum(output_tokens), round(sum(cost_usd)::numeric, 4) as usd "
                        "from m05_c01.usage_events where status = 'ok' group by 1, 2 order by usd desc limit 6").fetchall()
    print("tenant               feature              calls  out tokens   cost USD")
    for tenant, feature, n, tokens, usd in rows:
        print(f"{tenant:<20} {feature:<20} {n:>5} {tokens:>11} {usd:>10}")
    conn.execute("drop schema m05_c01 cascade")
