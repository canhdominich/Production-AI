import json

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import _data
import _redactkit

records = _data.load()
exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
tracer = provider.get_tracer("demo")

ALLOWED = {"gen_ai.operation.name", "gen_ai.tool.name", "gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens", "tenant.id", "text.length"}


def set_safe(span, key, value):
    if key in ALLOWED:
        span.set_attribute(key, value if not isinstance(value, str) else _redactkit.redact(value))


def trace_one(rec, safe):
    with tracer.start_as_current_span("retrieval") as span:
        if safe:
            set_safe(span, "gen_ai.operation.name", "retrieval")
            set_safe(span, "text.length", len(rec["text"]))
            set_safe(span, "gen_ai.retrieval.query.text", rec["text"])
        else:
            span.set_attribute("gen_ai.operation.name", "retrieval")
            span.set_attribute("gen_ai.retrieval.query.text", rec["text"])
    with tracer.start_as_current_span("execute_tool get_order") as span:
        args = json.dumps({"order_id": "AT310007", "note": rec["text"]}, ensure_ascii=False)
        if safe:
            set_safe(span, "gen_ai.tool.name", "get_order")
            set_safe(span, "gen_ai.tool.call.arguments", args)
        else:
            span.set_attribute("gen_ai.tool.name", "get_order")
            span.set_attribute("gen_ai.tool.call.arguments", args)


secrets = set(_data.secrets_of(records))
for label, safe in (("raw attributes", False), ("allowlist + redaction", True)):
    exporter.clear()
    for rec in records:
        trace_one(rec, safe)
    spans = exporter.get_finished_spans()
    blob = [json.dumps(dict(s.attributes), ensure_ascii=False) for s in spans]
    leaking = sum(1 for line in blob if any(v in line for v in secrets))
    print(f"{label:<22} spans {len(spans)}, spans carrying a phone or address: {leaking}")
    print("   keys on the spans (gen_ai. prefix removed):", ", ".join(sorted({k.removeprefix("gen_ai.") for s in spans for k in s.attributes})))
