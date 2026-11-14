import random
import time
from datetime import datetime, timezone

from _kit import MONTH_START, PRICE_VERSION, SCHEMA, PriceTable, connect, ensure_schema, generate

DAYS = 30
PER_DAY = 6000
LATENCY_MS_PER_TOKEN = {"small": 12, "medium": 20, "large": 35}
prices = PriceTable()
rnd = random.Random(7)
start = datetime.fromisoformat(MONTH_START).replace(tzinfo=timezone.utc).timestamp()
COLS = "request_id, attempt, ts, tenant_id, feature, role, model, tier, provider, status, prompt_tokens, cached_tokens, output_tokens, cost_usd, price_version, latency_ms"


def day_rows(d):
    weekend = (d + 3) % 7 in (5, 6)
    reqs = generate(int(PER_DAY * (0.7 if weekend else 1.0)), seed=100 + d)
    for r in reqs:
        tenant = r.tenant_id
        if r.feature == "weekly_report_agent" and d >= 20 and rnd.random() < 0.5:
            tenant = "unattributed"
        failed = rnd.random() < 0.02
        pt, ot = (0, 0) if failed else (r.prompt_tokens, r.output_tokens)
        cost = 0.0 if failed else prices.cost(r.model, pt, ot)
        yield (f"d{d:02d}-{r.request_id}", 1, start + d * 86400 + r.arrival_s, tenant, r.feature, r.role, r.model, r.tier, "fake",
               "server_error" if failed else "ok", pt, 0, ot, round(cost, 8), PRICE_VERSION, 0.0 if failed else 300 + ot * LATENCY_MS_PER_TOKEN[r.tier])
    if d == 17:
        for i in range(18000):
            ts = start + d * 86400 + 14 * 3600 + i * 0.9
            cost = prices.cost("fake-medium", 3000, 300)
            yield (f"d{d:02d}-loop-{i}", 1, ts, "br-xom-vui", "knowledge_assistant", "integration", "fake-medium", "medium", "fake", "ok", 3000, 0, 300, round(cost, 8), PRICE_VERSION, 7000.0)


with connect() as conn:
    ensure_schema(conn)
    conn.execute(f"TRUNCATE {SCHEMA}.usage_events RESTART IDENTITY")
    t0 = time.perf_counter()
    with conn.cursor() as cur:
        with cur.copy(f"COPY {SCHEMA}.usage_events ({COLS}) FROM STDIN") as cp:
            for d in range(DAYS):
                for row in day_rows(d):
                    cp.write_row((row[0], row[1], datetime.fromtimestamp(row[2], timezone.utc)) + row[3:])
    n, total, days = conn.execute(f"SELECT count(*), sum(cost_usd), count(DISTINCT ts::date) FROM {SCHEMA}.usage_events").fetchone()
    print(f"usage_events loaded: {n} rows over {days} days, total cost ${float(total):.2f}, price_version {PRICE_VERSION}")
    print("table size:", conn.execute(f"SELECT pg_size_pretty(pg_total_relation_size('{SCHEMA}.usage_events'))").fetchone()[0])
