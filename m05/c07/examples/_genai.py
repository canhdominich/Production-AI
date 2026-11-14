import json
import re
import zlib
import time
from pathlib import Path

import numpy as np
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import SpanKind, Status, StatusCode

from _support import BASE, DATA, PLATFORM  # noqa: F401
from common import estimate_tokens
from gateway_core import Gateway, GatewayRequest, ProviderClient, ProviderError

SNAPSHOT = json.loads((DATA / "genai_semconv_snapshot.json").read_text(encoding="utf-8"))
POLICY = (BASE.parent / "m04" / "data" / "policy.md").read_text(encoding="utf-8")


class JsonlSpanExporter(SpanExporter):
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")

    def export(self, spans):
        with self.path.open("a", encoding="utf-8") as f:
            for s in spans:
                ctx, parent = s.get_span_context(), s.parent
                f.write(json.dumps({
                    "trace_id": format(ctx.trace_id, "032x"), "span_id": format(ctx.span_id, "016x"),
                    "parent_span_id": format(parent.span_id, "016x") if parent else None,
                    "name": s.name, "kind": s.kind.name,
                    "start_ns": s.start_time, "end_ns": s.end_time,
                    "status": s.status.status_code.name,
                    "attributes": dict(s.attributes),
                    "resource": dict(s.resource.attributes),
                }, ensure_ascii=False) + "\n")
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass


def make_tracer(path, service="anhti-ai-api"):
    provider = TracerProvider(resource=Resource.create({"service.name": service, "service.version": "1.0.0"}))
    provider.add_span_processor(SimpleSpanProcessor(JsonlSpanExporter(path)))
    return provider.get_tracer("anhti.genai", "1.0.0"), provider


def read_spans(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


class ObservedGateway(Gateway):
    def call_provider(self, provider, model, req):
        result = super().call_provider(provider, model, req)
        req.finish_reason = result.finish_reason
        return result


def traced_chat(tracer, gw, req, capture_content=False, prompt_name=None, prompt_version=None):
    model = gw.prices.model_for(req.tier)
    with tracer.start_as_current_span(f"chat {model}", kind=SpanKind.CLIENT) as span:
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.provider.name", "fake")
        span.set_attribute("gen_ai.request.model", model)
        if req.max_tokens:
            span.set_attribute("gen_ai.request.max_tokens", req.max_tokens)
        span.set_attribute("anhti.tenant.id", req.tenant_id)
        span.set_attribute("anhti.feature", req.feature)
        if prompt_name:
            span.set_attribute("gen_ai.prompt.name", prompt_name)
            span.set_attribute("gen_ai.prompt.version", prompt_version)
        if capture_content:
            span.set_attribute("gen_ai.input.messages", json.dumps([{"role": m["role"], "parts": [{"type": "text", "content": m["content"]}]} for m in req.messages], ensure_ascii=False))
        try:
            resp = gw.handle(req)
        except ProviderError as e:
            span.set_attribute("error.type", e.kind)
            span.set_status(Status(StatusCode.ERROR, e.kind))
            raise
        rec = resp.record
        span.set_attribute("gen_ai.response.model", rec.model)
        span.set_attribute("gen_ai.response.id", rec.request_id)
        span.set_attribute("gen_ai.response.finish_reasons", [getattr(req, "finish_reason", "stop")])
        span.set_attribute("gen_ai.usage.input_tokens", rec.prompt_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", rec.output_tokens)
        span.set_attribute("anhti.cost.usd", round(rec.cost_usd, 8))
        if capture_content:
            span.set_attribute("gen_ai.output.messages", json.dumps([{"role": "assistant", "parts": [{"type": "text", "content": resp.text}], "finish_reason": getattr(req, "finish_reason", "stop")}], ensure_ascii=False))
        return resp


WORD = re.compile(r"\w+", re.U)


def _vec(text, dim=256):
    v = np.zeros(dim)
    for w in WORD.findall(text.lower()):
        v[zlib.crc32(w.encode()) % dim] += 1.0
    n = np.linalg.norm(v)
    return v / n if n else v


class PolicyIndex:
    def __init__(self):
        self.chunks = [c.strip() for c in re.split(r"\n\s*\n", POLICY) if c.strip().startswith("**CS-")]
        self.matrix = np.array([_vec(c) for c in self.chunks])

    def search(self, query, k=3):
        scores = self.matrix @ _vec(query)
        order = np.argsort(-scores)[:k]
        return [(int(i), float(scores[i]), self.chunks[i]) for i in order]


def traced_rag(tracer, gw, index, req, question, k=3, capture_content=False):
    with tracer.start_as_current_span("POST /ask", kind=SpanKind.SERVER) as root:
        root.set_attribute("http.request.method", "POST")
        root.set_attribute("http.route", "/ask")
        root.set_attribute("anhti.tenant.id", req.tenant_id)
        root.set_attribute("anhti.feature", req.feature)
        with tracer.start_as_current_span("retrieval", kind=SpanKind.INTERNAL) as r:
            r.set_attribute("gen_ai.operation.name", "retrieval")
            r.set_attribute("gen_ai.retrieval.top_k", k)
            if capture_content:
                r.set_attribute("gen_ai.retrieval.query.text", question)
            with tracer.start_as_current_span("embeddings anhti-embed-small", kind=SpanKind.CLIENT) as e:
                e.set_attribute("gen_ai.operation.name", "embeddings")
                e.set_attribute("gen_ai.provider.name", "local")
                e.set_attribute("gen_ai.request.model", "anhti-embed-small")
                e.set_attribute("gen_ai.usage.input_tokens", estimate_tokens(question))
            with tracer.start_as_current_span("SELECT chunks", kind=SpanKind.CLIENT) as q:
                q.set_attribute("db.system.name", "postgresql")
                q.set_attribute("db.operation.name", "SELECT")
                hits = index.search(question, k)
            r.set_attribute("anhti.retrieval.top_score", round(hits[0][1], 4))
            if capture_content:
                r.set_attribute("gen_ai.retrieval.documents", json.dumps([{"id": f"policy-{i}", "score": round(s, 4)} for i, s, _ in hits]))
        context = "\n".join(c for _, _, c in hits)
        req.messages = [{"role": "system", "content": "Answer only from the context.\n" + context}, {"role": "user", "content": question}]
        return traced_chat(tracer, gw, req, capture_content=capture_content, prompt_name="policy-answer", prompt_version="3"), hits


TOOLS = {
    "get_order": lambda args: {"order_id": args["order_id"], "status": "delivered_late", "minutes_late": 38},
    "refund_policy": lambda args: {"rule": "refund shipping fee when late over 30 minutes"},
}


def traced_agent(tracer, gw, req, steps=("get_order", "refund_policy"), fail_tool=None):
    with tracer.start_as_current_span("POST /jobs", kind=SpanKind.SERVER) as root:
        root.set_attribute("http.request.method", "POST")
        root.set_attribute("http.route", "/jobs")
        root.set_attribute("anhti.tenant.id", req.tenant_id)
        root.set_attribute("anhti.feature", req.feature)
        with tracer.start_as_current_span("invoke_agent weekly-report", kind=SpanKind.INTERNAL) as a:
            a.set_attribute("gen_ai.operation.name", "invoke_agent")
            a.set_attribute("gen_ai.agent.name", "weekly-report")
            a.set_attribute("gen_ai.conversation.id", f"job-{req.request_id}")
            results = []
            for i, name in enumerate(steps):
                traced_chat(tracer, gw, GatewayRequest(req.tenant_id, req.feature, req.messages, req.tier, req.role, f"{req.request_id}-p{i}", output_tokens=40))
                with tracer.start_as_current_span(f"execute_tool {name}", kind=SpanKind.INTERNAL) as t:
                    t.set_attribute("gen_ai.operation.name", "execute_tool")
                    t.set_attribute("gen_ai.tool.name", name)
                    t.set_attribute("gen_ai.tool.type", "function")
                    t.set_attribute("gen_ai.tool.call.id", f"call_{i}")
                    if name == fail_tool:
                        t.set_attribute("error.type", "TimeoutError")
                        t.set_status(Status(StatusCode.ERROR, "tool timeout"))
                        continue
                    results.append(TOOLS[name]({"order_id": "A-1001"}))
            return traced_chat(tracer, gw, GatewayRequest(req.tenant_id, req.feature, req.messages, req.tier, req.role, f"{req.request_id}-final", output_tokens=80))


def tree_lines(spans):
    by_parent = {}
    for s in spans:
        by_parent.setdefault(s["parent_span_id"], []).append(s)
    for v in by_parent.values():
        v.sort(key=lambda s: s["start_ns"])
    lines = []

    def walk(sp, depth):
        ms = (sp["end_ns"] - sp["start_ns"]) / 1e6
        mark = "  ERROR" if sp["status"] == "ERROR" else ""
        lines.append(f"{'  ' * depth}{sp['name']}  [{sp['kind']}] {ms:.1f} ms{mark}")
        for c in by_parent.get(sp["span_id"], []):
            walk(c, depth + 1)

    for root in by_parent.get(None, []):
        walk(root, 0)
    return lines


def validate_span(span, snapshot=SNAPSHOT, allow_content=False):
    attrs, problems = span["attributes"], []
    op = attrs.get("gen_ai.operation.name")
    if op is None:
        return []
    if op not in snapshot["operations"]:
        problems.append(f"unknown operation {op!r}")
    rule = snapshot["spans"].get(op)
    if rule:
        for key in rule["required"]:
            if key not in attrs:
                problems.append(f"missing required {key}")
        if span["kind"] != rule["kind"]:
            problems.append(f"kind {span['kind']} but the spec says {rule['kind']}")
    known = set(snapshot["gen_ai_attributes"])
    for key in attrs:
        if key in snapshot["older_names"]:
            problems.append(f"older name {key}, now {snapshot['older_names'][key]}")
        elif key.startswith("gen_ai.") and key not in known and not key.startswith("gen_ai.prompt.variable."):
            problems.append(f"unknown attribute {key}")
        elif key in snapshot["opt_in_content"] and not allow_content:
            problems.append(f"content attribute {key} recorded without opt-in")
    return problems


def normalize(attrs, snapshot=SNAPSHOT):
    return {snapshot["older_names"].get(k, k): v for k, v in attrs.items()}
