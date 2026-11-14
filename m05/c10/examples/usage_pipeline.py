from concurrent.futures import ThreadPoolExecutor

import httpx

from _kit import SCHEMA, Gateway, PgSink, PriceTable, connect, ensure_schema, fake_provider, generate
from gateway_core import GatewayRequest, ProviderClient, ProviderError


PROBE = "usage_probe"


class RecordingGateway(Gateway):
    def on_error(self, req, tenant, provider, error, started):
        self.record_failure(req, provider, self.prices.model_for(req.tier), error, started)
        raise error


def run(gateway_cls, base, conn, n=200, **faults):
    conn.execute(f"TRUNCATE {SCHEMA}.{PROBE} RESTART IDENTITY")
    httpx.post(base + "/admin/reset")
    httpx.post(base + "/admin/config", json={"faults": faults} if faults else {"faults": {}})
    prices = PriceTable()
    gw = gateway_cls([ProviderClient("fake", base)], prices=prices, sink=PgSink(conn, prices, PROBE))
    reqs = [r for r in generate(n * 2, seed=7) if r.feature != "weekly_report_agent"][:n]

    def send(r):
        q = GatewayRequest(r.tenant_id, r.feature, r.messages, r.tier, r.role, r.request_id, r.max_tokens, r.output_tokens)
        try:
            gw.handle(q)
            return "ok"
        except ProviderError as e:
            return e.kind

    with ThreadPoolExecutor(8) as pool:
        seen = list(pool.map(send, reqs))
    stats = httpx.get(base + "/admin/stats").json()
    row = conn.execute(f"SELECT count(*) FILTER (WHERE status = 'ok'), count(*), coalesce(sum(prompt_tokens), 0), coalesce(sum(output_tokens), 0), coalesce(sum(cost_usd), 0) FROM {SCHEMA}.{PROBE}").fetchone()
    return seen, stats, row


with connect() as conn, fake_provider() as base:
    ensure_schema(conn)
    conn.execute(f"CREATE TABLE IF NOT EXISTS {SCHEMA}.{PROBE} (LIKE {SCHEMA}.usage_events INCLUDING ALL)")
    seen, stats, row = run(Gateway, base, conn)
    print("healthy provider, 200 requests")
    print(f"  provider says: {stats['completed']} completed, {stats['prompt_tokens']} prompt tokens, {stats['output_tokens']} output tokens")
    print(f"  usage_events:  {row[0]} ok rows, {row[2]} prompt tokens, {row[3]} output tokens, ${float(row[4]):.4f}")
    print("  match:", (row[2], row[3]) == (stats["prompt_tokens"], stats["output_tokens"]))

    seen, stats, row = run(Gateway, base, conn, rate_limit=0.2)
    print("\n20% of calls answered 429, base gateway")
    print(f"  callers saw {seen.count('rate_limit')} errors, usage_events has {row[1]} rows for 200 requests")
    seen, stats, row = run(RecordingGateway, base, conn, rate_limit=0.2)
    print("same faults, gateway that records failures")
    print(f"  callers saw {seen.count('rate_limit')} errors, usage_events has {row[1]} rows ({row[0]} ok)")
    for status, n in conn.execute(f"SELECT status, count(*) FROM {SCHEMA}.{PROBE} GROUP BY status ORDER BY 2 DESC"):
        print(f"    status {status:10} {n}")
