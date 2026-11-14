import json
from contextlib import contextmanager

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest


class JsonlSpanExporter(SpanExporter):
    def __init__(self, path):
        self.path = path

    def export(self, spans):
        with open(self.path, "a", encoding="utf-8") as f:
            for s in spans:
                f.write(json.dumps({
                    "trace_id": format(s.context.trace_id, "032x"), "span_id": format(s.context.span_id, "016x"),
                    "parent_id": format(s.parent.span_id, "016x") if s.parent else None, "name": s.name,
                    "duration_ms": round((s.end_time - s.start_time) / 1e6, 3), "attributes": dict(s.attributes or {}),
                }) + "\n")
        return SpanExportResult.SUCCESS


class NullTelemetry:
    @contextmanager
    def span(self, name, **attrs):
        yield None

    def record(self, **event):
        pass

    def block(self, tenant_id, reason):
        pass


class Telemetry(NullTelemetry):
    def __init__(self, exporter=None):
        self.registry = CollectorRegistry()
        r = self.registry
        self.requests = Counter("anhti_requests_total", "Requests by outcome", ["tenant", "feature", "status"], registry=r)
        self.latency = Histogram("anhti_request_seconds", "End to end gateway latency", ["feature"], registry=r,
                                 buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10))
        self.cost = Counter("anhti_cost_usd_total", "Cost in USD", ["tenant"], registry=r)
        self.tokens = Counter("anhti_tokens_total", "Tokens", ["tenant", "kind"], registry=r)
        self.fallbacks = Counter("anhti_fallback_total", "Calls served by a fallback provider", ["provider"], registry=r)
        self.blocked = Counter("anhti_blocked_total", "Requests refused before the model", ["tenant", "reason"], registry=r)
        self.quality = Gauge("anhti_quality_score", "Online quality score by prompt version", ["prompt_version"], registry=r)
        self.exporter = exporter or InMemorySpanExporter()
        provider = TracerProvider(resource=Resource.create({"service.name": "anhti-platform"}))
        provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        self.tracer = provider.get_tracer("anhti.platform")

    @contextmanager
    def span(self, name, **attrs):
        with self.tracer.start_as_current_span(name, attributes=attrs) as s:
            yield s

    def record(self, **e):
        self.requests.labels(e["tenant_id"], e["feature"], e["status"]).inc()
        self.latency.labels(e["feature"]).observe(e["latency_ms"] / 1000)
        self.cost.labels(e["tenant_id"]).inc(e["cost_usd"])
        self.tokens.labels(e["tenant_id"], "prompt").inc(e["prompt_tokens"])
        self.tokens.labels(e["tenant_id"], "output").inc(e["output_tokens"])
        if e.get("fallback_used"):
            self.fallbacks.labels(e["provider"]).inc()

    def block(self, tenant_id, reason):
        self.blocked.labels(tenant_id, reason).inc()

    def render(self):
        return generate_latest(self.registry)

    def spans(self):
        return self.exporter.get_finished_spans() if hasattr(self.exporter, "get_finished_spans") else []
