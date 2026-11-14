import json
from pathlib import Path

from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

CONTENT_ATTRIBUTES = {"gen_ai.input.messages", "gen_ai.output.messages", "gen_ai.system_instructions", "gen_ai.tool.call.arguments", "gen_ai.tool.call.result", "gen_ai.retrieval.query.text"}


def span_name(operation, subject=None):
    return f"{operation} {subject}" if subject else operation


def inference_attributes(provider, model, input_tokens=None, output_tokens=None, finish_reason=None, max_tokens=None):
    attrs = {
        "gen_ai.operation.name": "chat",
        "gen_ai.provider.name": provider,
        "gen_ai.request.model": model,
        "gen_ai.response.model": model,
        "gen_ai.request.max_tokens": max_tokens,
        "gen_ai.usage.input_tokens": input_tokens,
        "gen_ai.usage.output_tokens": output_tokens,
        "gen_ai.response.finish_reasons": [finish_reason] if finish_reason else None,
    }
    return {k: v for k, v in attrs.items() if v is not None}


def tool_attributes(tool_name, call_id=None, error_type=None):
    attrs = {"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": tool_name, "gen_ai.tool.call.id": call_id, "error.type": error_type}
    return {k: v for k, v in attrs.items() if v is not None}


def validate_span(span, snapshot, allow_content=False):
    attrs, problems = span["attributes"], []
    op = attrs.get("gen_ai.operation.name")
    if op is None:
        return problems
    rule = snapshot["spans"].get(op)
    if rule:
        problems += [f"missing required {k}" for k in rule["required"] if k not in attrs]
    known = set(snapshot["attributes"])
    for key in attrs:
        if key in snapshot["older_names"]:
            problems.append(f"older name {key}, now {snapshot['older_names'][key]}")
        elif key.startswith("gen_ai.") and key not in known:
            problems.append(f"unknown attribute {key}")
        elif key in CONTENT_ATTRIBUTES and not allow_content:
            problems.append(f"content attribute {key} recorded without opt-in")
    return problems


class JsonlSpanExporter(SpanExporter):
    def __init__(self, path):
        self.path = Path(path)
        self.path.write_text("", encoding="utf-8")

    def export(self, spans):
        with self.path.open("a", encoding="utf-8") as f:
            for s in spans:
                ctx = s.get_span_context()
                f.write(json.dumps({
                    "trace_id": format(ctx.trace_id, "032x"), "span_id": format(ctx.span_id, "016x"),
                    "parent_span_id": format(s.parent.span_id, "016x") if s.parent else None,
                    "name": s.name, "kind": s.kind.name, "start_ns": s.start_time, "end_ns": s.end_time,
                    "status": s.status.status_code.name, "attributes": dict(s.attributes),
                }, ensure_ascii=False) + "\n")
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass


def trace_tree(spans):
    children = {}
    for s in spans:
        children.setdefault(s["parent_span_id"], []).append(s)
    lines = []

    def walk(span, depth):
        lines.append("  " * depth + span["name"])
        for child in sorted(children.get(span["span_id"], []), key=lambda c: c["start_ns"]):
            walk(child, depth + 1)

    for root in sorted(children.get(None, []), key=lambda c: c["start_ns"]):
        walk(root, 0)
    return lines


def token_totals(spans, snapshot):
    totals = {}
    for s in spans:
        attrs = {snapshot["older_names"].get(k, k): v for k, v in s["attributes"].items()}
        if "gen_ai.usage.input_tokens" not in attrs and "gen_ai.usage.output_tokens" not in attrs:
            continue
        row = totals.setdefault(attrs.get("anhti.feature", "unknown"), [0, 0])
        row[0] += attrs.get("gen_ai.usage.input_tokens", 0)
        row[1] += attrs.get("gen_ai.usage.output_tokens", 0)
    return {k: tuple(v) for k, v in totals.items()}
