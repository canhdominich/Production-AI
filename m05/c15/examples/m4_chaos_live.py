import time
from collections import Counter

import httpx
import psycopg
import redis

import _kit

BREAKER_COOLDOWN_S = 8


def phase(name, n, spacing):
    redis.Redis(host="127.0.0.1", port=5755, protocol=2).flushdb()
    tenants = list(_kit.SHARES)
    plan = [(i * spacing, tenants[i % len(tenants)]) for i in range(n)]
    rows, _ = _kit.drive(plan)
    codes = Counter(r["status"] for r in rows)
    served = [r for r in rows if r["status"] == 200]
    print(f"{name:34}{len(rows):>4}{codes.get(200, 0):>5}{codes.get(503, 0):>5}{sum(1 for r in served if r['fallback']):>6}"
          f"{_kit.pct([r['seconds'] for r in rows], 50) * 1000:>8.0f}ms{_kit.pct([r['seconds'] for r in rows], 95) * 1000:>8.0f}ms")
    return rows


def faults(url, spec):
    httpx.post(url + "/admin/config", json={"faults": spec, "timeout_hang_s": 120.0})


_kit.reset_stack_state()
with psycopg.connect(_kit.PG_DSN, autocommit=True) as pg:
    pg.execute("TRUNCATE m05_c15.usage_events")
print(f"{'phase':36}{'sent':>4}{'200':>5}{'503':>5}{'fallb':>6}{'p50':>10}{'p95':>10}")
phase("1 healthy", 40, 0.12)
faults(_kit.PRIMARY_ADMIN, {"error_500": 0.3, "rate_limit": 0.2})
phase("2 primary: 30% 500 and 20% 429", 40, 0.12)
faults(_kit.PRIMARY_ADMIN, {})
time.sleep(BREAKER_COOLDOWN_S + 1)
faults(_kit.PRIMARY_ADMIN, {"timeout": 1.0})
rows = phase("3 primary hangs (client timeout 5 s)", 20, 0.5)
print("   first 5 latencies (s):", [round(r["seconds"], 1) for r in rows[:5]], "| last 5:", [round(r["seconds"], 1) for r in rows[-5:]])
faults(_kit.SECONDARY_ADMIN, {"error_500": 1.0})
phase("4 both providers fail", 15, 0.3)
faults(_kit.PRIMARY_ADMIN, {})
faults(_kit.SECONDARY_ADMIN, {})
time.sleep(BREAKER_COOLDOWN_S + 1)
phase("5 faults removed, breaker probes", 20, 0.12)
with psycopg.connect(_kit.PG_DSN) as pg:
    rows = pg.execute("SELECT status, provider, fallback_used, attempts, count(*) FROM m05_c15.usage_events GROUP BY 1, 2, 3, 4 ORDER BY 5 DESC, 1, 2, 3, 4").fetchall()
print("\nusage_events grouped (status, provider, fallback, attempts, count):")
for r in rows:
    print("  ", r)
