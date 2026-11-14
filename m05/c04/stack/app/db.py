import psycopg
import redis

from app import settings

DDL = f"""
create schema if not exists {settings.SCHEMA};
create table if not exists {settings.SCHEMA}.usage_events (
    request_id text primary key, tenant_id text not null, feature text not null, model text not null,
    prompt_tokens int not null, output_tokens int not null, cost_usd double precision not null,
    created_at timestamptz not null default now());
create table if not exists {settings.SCHEMA}.jobs (
    job_id text primary key, tenant_id text not null, week text not null, status text not null default 'queued',
    result text, created_at timestamptz not null default now(), finished_at timestamptz);
"""


def connect():
    return psycopg.connect(settings.DATABASE_URL, autocommit=True)


def redis_client():
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def migrate():
    with connect() as conn:
        conn.execute(DDL)


def save_usage(conn, rec):
    conn.execute(
        f"insert into {settings.SCHEMA}.usage_events (request_id, tenant_id, feature, model, prompt_tokens, output_tokens, cost_usd) "
        "values (%s, %s, %s, %s, %s, %s, %s) on conflict do nothing",
        (rec.request_id, rec.tenant_id, rec.feature, rec.model, rec.prompt_tokens, rec.output_tokens, rec.cost_usd),
    )
