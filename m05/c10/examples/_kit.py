import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import httpx
import psycopg

HERE = Path(__file__).resolve().parent
PLATFORM = HERE.parents[1] / "platform"
if str(PLATFORM) not in sys.path:
    sys.path.insert(0, str(PLATFORM))

from common import percentile
from gateway_core import Gateway, PriceTable, TenantRegistry, UsageRecord, UsageSink
from workload import generate

PORT_PROVIDER = 5701
PORT_REDIS = 5702
DSN = "host=localhost port=55432 dbname=anhti user=anhti password=anhti"
SCHEMA = "m05_c10"
PRICE_VERSION = "illustrative-v1"
MONTH_START = "2026-10-01"
OUT_DIR = HERE.parent / "data" / "out"


def connect():
    conn = psycopg.connect(DSN, autocommit=True)
    conn.execute("SET TIME ZONE 'UTC'")
    return conn


def ensure_schema(conn):
    conn.execute((HERE / "schema.sql").read_text(encoding="utf-8"))


INSERT_SQL = f"""
INSERT INTO {SCHEMA}.TABLE
 (request_id, attempt, ts, tenant_id, feature, role, model, tier, provider, status,
  prompt_tokens, cached_tokens, output_tokens, cost_usd, price_version, latency_ms)
VALUES (%s, %s, to_timestamp(%s), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (request_id, attempt) DO NOTHING
"""


def row_of(rec, prices, attempt=1):
    return (rec.request_id, attempt, rec.ts, rec.tenant_id, rec.feature, rec.role, rec.model, prices.tier_of(rec.model), rec.provider,
            rec.status, rec.prompt_tokens, rec.cached_tokens, rec.output_tokens, round(rec.cost_usd, 8), PRICE_VERSION, rec.latency_ms)


class PgSink(UsageSink):
    def __init__(self, conn, prices, table="usage_events"):
        super().__init__()
        self.conn = conn
        self.prices = prices
        self.sql = INSERT_SQL.replace("TABLE", table)

    def write(self, record):
        super().write(record)
        self.conn.execute(self.sql, row_of(record, self.prices))


@contextmanager
def fake_provider(scale=0.02, port=PORT_PROVIDER, **config):
    env = dict(os.environ, FAKE_TIME_SCALE=str(scale), FAKE_SEED="42")
    proc = subprocess.Popen([sys.executable, str(PLATFORM / "fake_provider.py"), "--port", str(port)], env=env, cwd=str(PLATFORM),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                if httpx.get(base + "/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.1)
        if config:
            httpx.post(base + "/admin/config", json=config, timeout=5).raise_for_status()
        yield base
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@contextmanager
def redis_server(port=PORT_REDIS):
    proc = subprocess.Popen(["redis-server", "--port", str(port), "--save", "", "--appendonly", "no", "--bind", "127.0.0.1"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        import redis
        r = redis.Redis(port=port, protocol=2)
        for _ in range(50):
            try:
                r.ping()
                break
            except redis.ConnectionError:
                time.sleep(0.1)
        yield port
    finally:
        proc.terminate()
        proc.wait(timeout=10)
