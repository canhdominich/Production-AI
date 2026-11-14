import hashlib
import json
from _sec import SCHEMA, pg

conn = pg()
conn.execute("drop table if exists audit_log")
conn.execute("""create table audit_log (
    id bigserial primary key, ts timestamptz not null, tenant_id text not null, actor text not null,
    action text not null, detail jsonb not null, prev_hash text not null, row_hash text not null)""")
GENESIS = "0" * 64


def digest(prev, ts, tenant, actor, action, detail):
    payload = json.dumps([prev, ts, tenant, actor, action, detail], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def append(ts, tenant, actor, action, detail):
    row = conn.execute("select row_hash from audit_log order by id desc limit 1").fetchone()
    prev = row[0] if row else GENESIS
    h = digest(prev, ts, tenant, actor, action, detail)
    conn.execute("insert into audit_log (ts, tenant_id, actor, action, detail, prev_hash, row_hash) values (%s,%s,%s,%s,%s,%s,%s)",
                 (ts, tenant, actor, action, json.dumps(detail), prev, h))


def verify():
    prev = GENESIS
    for id_, ts, tenant, actor, action, detail, p, h in conn.execute(
            "select id, to_char(ts at time zone 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"'), tenant_id, actor, action, detail, prev_hash, row_hash from audit_log order by id"):
        if p != prev or digest(prev, ts, tenant, actor, action, detail) != h:
            return id_
        prev = h
    return None


events = [
    ("2026-11-14T08:00:00Z", "br-cau-go", "cg-03", "login", {"ip": "203.0.113.7"}),
    ("2026-11-14T08:05:10Z", "br-cau-go", "cg-03", "feature.use", {"feature": "weekly_report_agent"}),
    ("2026-11-14T08:07:42Z", "br-cau-go", "cg-int", "api_key.use", {"key_id": "a1b2c3d4"}),
    ("2026-11-14T09:30:00Z", "br-ben-song", "bs-02", "export.history", {"rows": 340}),
    ("2026-11-14T09:41:09Z", "br-ben-song", "bs-02", "api_key.revoke", {"key_id": "9f8e7d6c"}),
    ("2026-11-14T10:02:31Z", "br-dau-pho", "dp-03", "customer.erase", {"customer": "c-00417"}),
]
for e in events:
    append(*e)
print("rows written:", conn.execute("select count(*) from audit_log").fetchone()[0])
print("verify untouched chain :", verify())
conn.execute("update audit_log set detail = '{\"rows\": 3}' where action = 'export.history'")
print("row 4 edited (340 to 3):", "first bad row id", verify())
conn.execute("update audit_log set detail = '{\"rows\": 340}' where action = 'export.history'")
print("edit undone            :", verify())
conn.execute("delete from audit_log where id = 5")
print("row 5 deleted          :", "first bad row id", verify())
conn.execute(f"drop table audit_log")
print("schema:", SCHEMA)
