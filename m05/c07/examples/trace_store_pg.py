import json

import psycopg
from opentelemetry.trace import SpanKind

from _genai import ObservedGateway, make_tracer, read_spans, traced_chat
from _support import DATA, provider
from gateway_core import GatewayRequest, ProviderClient
from workload import generate

OUT = DATA / "traces_store.jsonl"
tracer, tp = make_tracer(OUT)
with provider(5675, time_scale=0.02) as url:
    gw = ObservedGateway([ProviderClient("fake", url)])
    for i, r in enumerate(generate(60, seed=42)):
        version = "1" if i % 2 == 0 else "2"
        wants = r.output_tokens * (3 if version == "2" else 1)
        gr = GatewayRequest(r.tenant_id, r.feature, r.messages, r.tier, r.role, r.request_id, max_tokens=300, output_tokens=wants)
        with tracer.start_as_current_span(f"POST /{r.feature}", kind=SpanKind.SERVER):
            traced_chat(tracer, gw, gr, prompt_name="reply-style", prompt_version=version)
tp.shutdown()

SCHEMA = """
DROP SCHEMA IF EXISTS m05_c07 CASCADE;
CREATE SCHEMA m05_c07;
CREATE TABLE m05_c07.spans (span_id text PRIMARY KEY, trace_id text, parent_id text, name text, duration_ms double precision, attrs jsonb);
CREATE TABLE m05_c07.prompts (name text, version text, body text, PRIMARY KEY (name, version));
CREATE TABLE m05_c07.scores (trace_id text, name text, value double precision, source text);
CREATE VIEW m05_c07.calls AS
  SELECT trace_id, duration_ms, attrs->>'anhti.tenant.id' AS tenant, attrs->>'anhti.feature' AS feature,
         attrs->>'gen_ai.prompt.name' AS prompt, attrs->>'gen_ai.prompt.version' AS version,
         (attrs->>'gen_ai.usage.output_tokens')::int AS out_tokens, attrs->'gen_ai.response.finish_reasons'->>0 AS finish,
         (attrs->>'anhti.cost.usd')::double precision AS cost
  FROM m05_c07.spans WHERE attrs->>'gen_ai.operation.name' = 'chat';
"""
with psycopg.connect("postgresql://anhti:anhti@localhost:55432/anhti", autocommit=True) as db:
    db.execute(SCHEMA)
    for s in read_spans(OUT):
        db.execute("INSERT INTO m05_c07.spans VALUES (%s,%s,%s,%s,%s,%s)",
                   (s["span_id"], s["trace_id"], s["parent_span_id"], s["name"], (s["end_ns"] - s["start_ns"]) / 1e6, json.dumps(s["attributes"])))
    db.execute("INSERT INTO m05_c07.prompts VALUES ('reply-style','1','Answer briefly.'), ('reply-style','2','Answer in detail with every step.')")
    db.execute("INSERT INTO m05_c07.scores SELECT trace_id, 'complete', CASE WHEN finish = 'length' THEN 0 ELSE 1 END, 'rule:finish_reason' FROM m05_c07.calls")
    print("spans stored:", db.execute("SELECT count(*) FROM m05_c07.spans").fetchone()[0], "| scores stored:", db.execute("SELECT count(*) FROM m05_c07.scores").fetchone()[0])
    print("\nOne query joins trace, prompt version and score:")
    print(f"{'prompt':14}{'calls':>6}{'complete':>10}{'avg out tokens':>16}{'cost USD':>10}")
    rows = db.execute("""
        SELECT c.prompt || '@' || c.version, count(*), round(avg(s.value)::numeric, 2), round(avg(c.out_tokens)::numeric), round(sum(c.cost)::numeric, 4)
        FROM m05_c07.calls c JOIN m05_c07.scores s USING (trace_id) JOIN m05_c07.prompts p ON p.name = c.prompt AND p.version = c.version
        GROUP BY c.prompt, c.version ORDER BY c.version""").fetchall()
    for r in rows:
        print(f"{r[0]:14}{r[1]:>6}{r[2]:>10}{r[3]:>16}{r[4]:>10}")
    print("\nWorst traces (score 0), longest output first:")
    for r in db.execute("""
        SELECT left(c.trace_id, 8), c.tenant, c.feature, c.version, c.out_tokens FROM m05_c07.calls c JOIN m05_c07.scores s USING (trace_id)
        WHERE s.value = 0 ORDER BY c.out_tokens DESC, c.trace_id LIMIT 4"""):
        print("  ", *r)
