import html
import json

from _kit import HERE, MONTH_START, OUT_DIR, SCHEMA, TenantRegistry, connect, ensure_schema

MONTH = (MONTH_START, "2026-11-01")
FEATURES = ["chat", "knowledge_assistant", "weekly_report_agent"]

MATRIX = f"""
SELECT tenant_id,
       coalesce(sum(cost_usd) FILTER (WHERE feature = 'chat'), 0),
       coalesce(sum(cost_usd) FILTER (WHERE feature = 'knowledge_assistant'), 0),
       coalesce(sum(cost_usd) FILTER (WHERE feature = 'weekly_report_agent'), 0),
       sum(cost_usd)
FROM {SCHEMA}.v_cost_daily
WHERE day >= %s AND day < %s
GROUP BY tenant_id
ORDER BY sum(cost_usd) DESC
"""

SPIKES = f"""
WITH d AS (SELECT day, tenant_id, sum(cost_usd) AS c FROM {SCHEMA}.v_cost_daily GROUP BY 1, 2),
     m AS (SELECT tenant_id, percentile_cont(0.5) WITHIN GROUP (ORDER BY c) AS med FROM d GROUP BY 1)
SELECT d.day::date, d.tenant_id, d.c, m.med, d.c / m.med
FROM d JOIN m USING (tenant_id)
WHERE d.c > 2 * m.med AND d.tenant_id <> 'unattributed'
ORDER BY d.c / m.med DESC
"""

PER_CALL = f"""
SELECT feature,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY cost_usd),
       percentile_cont(0.95) WITHIN GROUP (ORDER BY cost_usd),
       max(cost_usd)
FROM {SCHEMA}.usage_events WHERE status = 'ok' AND ts >= '2026-10-02' AND ts < '2026-10-03' GROUP BY feature ORDER BY 3 DESC
"""

with connect() as conn:
    ensure_schema(conn)
    conn.execute((HERE / "views.sql").read_text(encoding="utf-8"))
    tenants = {t.tenant_id: t for t in TenantRegistry().all()}
    rows = conn.execute(MATRIX, MONTH).fetchall()
    grand = sum(float(r[4]) for r in rows)
    print(f"October 2026, cost by tenant and feature (USD, illustrative prices), total ${grand:.2f}")
    print(f"{'tenant':20}{'chat':>8}{'knowledge':>10}{'report':>8}{'total':>9}{'budget':>8}{'used':>7}")
    cards = []
    for t, c, k, w, tot in rows:
        budget = tenants[t].monthly_budget_usd if t in tenants else None
        used = f"{float(tot) / budget:6.0%}" if budget else "     -"
        print(f"{t:20}{float(c):8.2f}{float(k):10.2f}{float(w):8.2f}{float(tot):9.2f}{budget or 0:8.0f}{used}")
        cards.append((t, float(c), float(k), float(w), float(tot), budget))
    unattributed = next((float(r[4]) for r in rows if r[0] == "unattributed"), 0.0)
    print(f"unallocated cost: ${unattributed:.2f} ({unattributed / grand:.1%} of the month)")

    print("\ndays when a tenant cost more than twice its own median day")
    for day, t, c, med, ratio in conn.execute(SPIKES):
        print(f"  {day}  {t:12} ${float(c):7.2f} against median ${float(med):6.2f}  ({float(ratio):.1f}x)")

    print("\ncost of one successful call on 2 October, an ordinary day (USD)")
    for f, p50, p95, mx in conn.execute(PER_CALL):
        print(f"  {f:22} p50 {float(p50):.5f}  p95 {float(p95):.5f}  max {float(mx):.5f}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    body = []
    for t, c, k, w, tot, budget in sorted(cards, key=lambda x: -x[4]):
        pct = min(100.0, tot / budget * 100) if budget else 0
        color = "#EF4444" if pct >= 100 else "#F97316" if pct >= 80 else "#2563EB"
        body.append(f"<tr><td>{html.escape(t)}</td><td>{c:.2f}</td><td>{k:.2f}</td><td>{w:.2f}</td><td><b>{tot:.2f}</b></td>"
                    f"<td><div class='bar'><div style='width:{pct:.0f}%;background:{color}'></div></div>{pct:.0f}%</td></tr>")
    page = ("<!doctype html><meta charset='utf-8'><title>Cost by tenant, October 2026</title>"
            "<style>body{font:14px sans-serif;margin:24px}td,th{padding:6px 10px;border-bottom:1px solid #ddd;text-align:right}"
            "td:first-child,th:first-child{text-align:left}.bar{display:inline-block;width:120px;height:10px;background:#eee;margin-right:8px}"
            ".bar div{height:10px}</style><h1>Cost by tenant, October 2026 (USD, illustrative prices)</h1>"
            "<table><tr><th>tenant</th><th>chat</th><th>knowledge</th><th>report</th><th>total</th><th>budget used</th></tr>" + "".join(body) + "</table>")
    (OUT_DIR / "cost_dashboard.html").write_text(page, encoding="utf-8")
    print(f"\nstatic page written: {len(page)} bytes, {len(body)} tenant rows")
