import threading
import time
from collections import defaultdict
from datetime import datetime, timezone


def month_key(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m")


class MemoryUsageStore:
    def __init__(self):
        self.events = []
        self._spent = defaultdict(float)
        self._lock = threading.Lock()

    def add(self, event):
        with self._lock:
            self.events.append(event)
            self._spent[(event["tenant_id"], month_key(event["ts"]))] += event["cost_usd"]

    def month_spend(self, tenant_id, month):
        return self._spent[(tenant_id, month)]

    def summary(self, tenant_id, month):
        rows = [e for e in self.events if e["tenant_id"] == tenant_id and month_key(e["ts"]) == month]
        by_feature = defaultdict(lambda: {"requests": 0, "cost_usd": 0.0, "tokens": 0})
        for e in rows:
            f = by_feature[e["feature"]]
            f["requests"] += 1
            f["cost_usd"] += e["cost_usd"]
            f["tokens"] += e["prompt_tokens"] + e["output_tokens"]
        return {"tenant_id": tenant_id, "month": month, "requests": len(rows), "cost_usd": round(sum(e["cost_usd"] for e in rows), 6),
                "by_feature": {k: {**v, "cost_usd": round(v["cost_usd"], 6)} for k, v in by_feature.items()}}


DDL = """
CREATE TABLE IF NOT EXISTS {schema}.usage_events (
    id bigserial PRIMARY KEY,
    request_id text NOT NULL,
    ts timestamptz NOT NULL,
    tenant_id text NOT NULL,
    user_id text NOT NULL,
    feature text NOT NULL,
    model text NOT NULL,
    provider text NOT NULL,
    status text NOT NULL,
    prompt_tokens int NOT NULL,
    output_tokens int NOT NULL,
    cost_usd numeric(14, 9) NOT NULL,
    latency_ms double precision NOT NULL,
    attempts int NOT NULL,
    fallback_used boolean NOT NULL,
    prompt_version text NOT NULL
);
CREATE INDEX IF NOT EXISTS usage_tenant_month ON {schema}.usage_events (tenant_id, ts);
"""

COLUMNS = ("request_id", "ts", "tenant_id", "user_id", "feature", "model", "provider", "status", "prompt_tokens", "output_tokens",
           "cost_usd", "latency_ms", "attempts", "fallback_used", "prompt_version")


class PgUsageStore:
    def __init__(self, dsn, schema="m05_c15"):
        import psycopg
        self.schema = schema
        self.conn = psycopg.connect(dsn, autocommit=True)
        self.conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        self.conn.execute(DDL.format(schema=schema))

    def add(self, event):
        values = [datetime.fromtimestamp(event[c], tz=timezone.utc) if c == "ts" else event[c] for c in COLUMNS]
        marks = ", ".join(["%s"] * len(COLUMNS))
        self.conn.execute(f"INSERT INTO {self.schema}.usage_events ({', '.join(COLUMNS)}) VALUES ({marks})", values)

    def month_spend(self, tenant_id, month):
        row = self.conn.execute(
            f"SELECT coalesce(sum(cost_usd), 0) FROM {self.schema}.usage_events "
            "WHERE tenant_id = %s AND to_char(ts AT TIME ZONE 'UTC', 'YYYY-MM') = %s", (tenant_id, month)).fetchone()
        return float(row[0])

    def summary(self, tenant_id, month):
        rows = self.conn.execute(
            f"SELECT feature, count(*), sum(cost_usd), sum(prompt_tokens + output_tokens) FROM {self.schema}.usage_events "
            "WHERE tenant_id = %s AND to_char(ts AT TIME ZONE 'UTC', 'YYYY-MM') = %s GROUP BY feature ORDER BY feature", (tenant_id, month)).fetchall()
        by_feature = {f: {"requests": n, "cost_usd": round(float(c), 6), "tokens": int(t)} for f, n, c, t in rows}
        return {"tenant_id": tenant_id, "month": month, "requests": sum(v["requests"] for v in by_feature.values()),
                "cost_usd": round(sum(v["cost_usd"] for v in by_feature.values()), 6), "by_feature": by_feature}

    def drop(self):
        self.conn.execute(f"DROP SCHEMA IF EXISTS {self.schema} CASCADE")


def now():
    return time.time()
