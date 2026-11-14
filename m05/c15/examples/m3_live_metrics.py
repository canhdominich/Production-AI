import time

import httpx
import psycopg

import _kit

KEYS = {"br-dau-pho": "demo-key-dau-pho", "br-khu-cong-nghiep": "demo-key-khu-cong-nghiep", "br-cau-go": "demo-key-cau-go",
        "br-xom-vui": "demo-key-xom-vui", "br-ben-song": "demo-key-ben-song"}
PLAN = {"br-dau-pho": 12, "br-khu-cong-nghiep": 10, "br-cau-go": 8, "br-xom-vui": 6, "br-ben-song": 4}
from anhti_platform.usage import PgUsageStore

store = PgUsageStore(_kit.PG_DSN)
store.conn.execute("TRUNCATE m05_c15.usage_events")
store.conn.close()


def scrape(name):
    out = {}
    for line in httpx.get(_kit.API + "/metrics").text.splitlines():
        if line.startswith(name + "{"):
            labels, value = line.rsplit(" ", 1)
            tenant = labels.split('tenant="')[1].split('"')[0]
            out[tenant] = out.get(tenant, 0.0) + float(value)
    return out


req0 = scrape("anhti_requests_total")
cost0 = scrape("anhti_cost_usd_total")
http = httpx.Client(base_url=_kit.API, timeout=30)
for t, n in PLAN.items():
    for i in range(n):
        http.post("/v1/chat", json={"message": f"don {i} bao gio toi", "tier": "large" if i % 4 == 0 else "medium"}, headers={"x-api-key": KEYS[t]})

req = {k: v - req0.get(k, 0) for k, v in scrape("anhti_requests_total").items()}
cost = {k: v - cost0.get(k, 0) for k, v in scrape("anhti_cost_usd_total").items()}
print("Metrics endpoint (what Prometheus scrapes), per tenant:")
for t in PLAN:
    print(f"  {t:20} requests {req.get(t, 0):4.0f}  cost {cost.get(t, 0):.6f} USD")
with psycopg.connect(_kit.PG_DSN) as pg:
    rows = pg.execute("SELECT tenant_id, count(*), sum(cost_usd), sum(prompt_tokens + output_tokens) FROM m05_c15.usage_events "
                      "GROUP BY 1 ORDER BY 1").fetchall()
print("PostgreSQL usage_events, per tenant:")
for t, n, c, tok in rows:
    print(f"  {t:20} requests {n:4d}  cost {float(c):.6f} USD  tokens {tok}")
worst = max(abs(cost.get(t, 0) - float(c)) for t, _, c, _ in rows)
print("largest gap between the two sources (USD):", f"{worst:.0e}")
