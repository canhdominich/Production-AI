CREATE SCHEMA IF NOT EXISTS m05_c10;

CREATE TABLE IF NOT EXISTS m05_c10.usage_events (
    event_id       bigserial PRIMARY KEY,
    request_id     text           NOT NULL,
    attempt        int            NOT NULL DEFAULT 1,
    ts             timestamptz    NOT NULL,
    tenant_id      text           NOT NULL,
    feature        text           NOT NULL,
    role           text           NOT NULL DEFAULT '',
    model          text           NOT NULL,
    tier           text           NOT NULL CHECK (tier IN ('small', 'medium', 'large')),
    provider       text           NOT NULL,
    status         text           NOT NULL,
    prompt_tokens  int            NOT NULL DEFAULT 0 CHECK (prompt_tokens >= 0),
    cached_tokens  int            NOT NULL DEFAULT 0 CHECK (cached_tokens >= 0),
    output_tokens  int            NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),
    cost_usd       numeric(14, 8) NOT NULL DEFAULT 0 CHECK (cost_usd >= 0),
    price_version  text           NOT NULL,
    latency_ms     real           NOT NULL DEFAULT 0,
    UNIQUE (request_id, attempt)
);

CREATE INDEX IF NOT EXISTS usage_events_tenant_ts ON m05_c10.usage_events (tenant_id, ts);
CREATE INDEX IF NOT EXISTS usage_events_feature_ts ON m05_c10.usage_events (feature, ts);
