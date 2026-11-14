import json
import threading

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult


class JsonlExporter(SpanExporter):
    def __init__(self, path):
        self.path, self.lock = path, threading.Lock()

    def export(self, spans):
        with self.lock, open(self.path, "a", encoding="utf-8") as f:
            for s in spans:
                ctx = s.get_span_context()
                f.write(json.dumps({"name": s.name, "service": s.resource.attributes["service.name"], "kind": s.kind.name,
                                    "trace_id": format(ctx.trace_id, "032x"), "span_id": format(ctx.span_id, "016x"),
                                    "parent_id": format(s.parent.span_id, "016x") if s.parent else None,
                                    "start_ns": s.start_time, "end_ns": s.end_time, "status": s.status.status_code.name,
                                    "attributes": {k: v for k, v in s.attributes.items()}}, ensure_ascii=False, default=str) + "\n")
        return SpanExportResult.SUCCESS


def make_tracer(service, exporter):
    provider = TracerProvider(resource=Resource.create({"service.name": service}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer("anhti.m05.c08")


def otel_ids():
    ctx = trace.get_current_span().get_span_context()
    if not ctx.is_valid:
        return {}
    return {"trace_id": format(ctx.trace_id, "032x"), "span_id": format(ctx.span_id, "016x")}
