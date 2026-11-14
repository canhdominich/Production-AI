import json

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace import SpanKind

import otel_genai as og

SNAPSHOT = {
    "attributes": ["gen_ai.operation.name", "gen_ai.provider.name", "gen_ai.request.model", "gen_ai.response.model", "gen_ai.request.max_tokens",
                   "gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens", "gen_ai.response.finish_reasons", "gen_ai.tool.name",
                   "gen_ai.tool.call.id", "gen_ai.input.messages", "gen_ai.output.messages"],
    "older_names": {"gen_ai.system": "gen_ai.provider.name", "gen_ai.usage.prompt_tokens": "gen_ai.usage.input_tokens",
                    "gen_ai.usage.completion_tokens": "gen_ai.usage.output_tokens"},
    "spans": {"chat": {"required": ["gen_ai.operation.name", "gen_ai.provider.name"]},
              "execute_tool": {"required": ["gen_ai.operation.name", "gen_ai.tool.name"]}},
}


def span(name, attrs, sid="a", parent=None, start=0):
    return {"trace_id": "t", "span_id": sid, "parent_span_id": parent, "name": name, "kind": "CLIENT", "start_ns": start, "end_ns": start + 5, "status": "UNSET", "attributes": attrs}


def test_span_name():
    assert og.span_name("chat", "fake-small") == "chat fake-small"
    assert og.span_name("retrieval") == "retrieval"
    assert og.span_name("execute_tool", "get_order") == "execute_tool get_order"


def test_inference_attributes_current_names():
    a = og.inference_attributes("fake", "fake-small", 13, 60, "stop", 300)
    assert a["gen_ai.operation.name"] == "chat"
    assert a["gen_ai.provider.name"] == "fake"
    assert a["gen_ai.request.model"] == a["gen_ai.response.model"] == "fake-small"
    assert a["gen_ai.usage.input_tokens"] == 13 and a["gen_ai.usage.output_tokens"] == 60
    assert a["gen_ai.response.finish_reasons"] == ["stop"]
    assert "gen_ai.system" not in a and "gen_ai.usage.prompt_tokens" not in a


def test_inference_attributes_omit_unknown_values():
    a = og.inference_attributes("fake", "fake-small")
    assert set(a) == {"gen_ai.operation.name", "gen_ai.provider.name", "gen_ai.request.model", "gen_ai.response.model"}


def test_tool_attributes():
    ok = og.tool_attributes("get_order", "call_1")
    assert ok == {"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "get_order", "gen_ai.tool.call.id": "call_1"}
    assert og.tool_attributes("get_order", error_type="TimeoutError")["error.type"] == "TimeoutError"


def test_validate_good_span():
    s = span("chat fake-small", og.inference_attributes("fake", "fake-small", 1, 2, "stop"))
    assert og.validate_span(s, SNAPSHOT) == []


def test_validate_older_names_and_missing_required():
    s = span("chat x", {"gen_ai.operation.name": "chat", "gen_ai.system": "fake", "gen_ai.usage.prompt_tokens": 5})
    problems = og.validate_span(s, SNAPSHOT)
    assert "missing required gen_ai.provider.name" in problems
    assert "older name gen_ai.system, now gen_ai.provider.name" in problems
    assert "older name gen_ai.usage.prompt_tokens, now gen_ai.usage.input_tokens" in problems


def test_validate_unknown_attribute_and_other_namespaces():
    s = span("chat x", {**og.inference_attributes("fake", "m"), "gen_ai.usage.total_tokens": 9, "anhti.tenant.id": "br-cau-go", "error.type": "timeout"})
    assert og.validate_span(s, SNAPSHOT) == ["unknown attribute gen_ai.usage.total_tokens"]


def test_validate_content_needs_opt_in():
    s = span("chat x", {**og.inference_attributes("fake", "m"), "gen_ai.input.messages": "[]"})
    assert og.validate_span(s, SNAPSHOT) == ["content attribute gen_ai.input.messages recorded without opt-in"]
    assert og.validate_span(s, SNAPSHOT, allow_content=True) == []


def test_validate_tool_requires_name():
    s = span("execute_tool", {"gen_ai.operation.name": "execute_tool"})
    assert og.validate_span(s, SNAPSHOT) == ["missing required gen_ai.tool.name"]


def test_validate_ignores_spans_without_operation():
    assert og.validate_span(span("POST /ask", {"http.route": "/ask"}), SNAPSHOT) == []


def test_exporter_writes_parent_links(tmp_path):
    path = tmp_path / "t.jsonl"
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(og.JsonlSpanExporter(path)))
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("POST /ask", kind=SpanKind.SERVER):
        with tracer.start_as_current_span("chat fake-small", kind=SpanKind.CLIENT) as child:
            child.set_attribute("gen_ai.response.finish_reasons", ["stop"])
            child.set_attribute("gen_ai.usage.input_tokens", 7)
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    assert [r["name"] for r in rows] == ["chat fake-small", "POST /ask"]
    root = rows[1]
    assert root["parent_span_id"] is None and rows[0]["parent_span_id"] == root["span_id"]
    assert rows[0]["trace_id"] == root["trace_id"] and rows[0]["kind"] == "CLIENT"
    assert rows[0]["attributes"] == {"gen_ai.response.finish_reasons": ["stop"], "gen_ai.usage.input_tokens": 7}


def test_trace_tree_orders_children_by_start():
    spans = [span("chat", {}, "c", "r", 30), span("retrieval", {}, "b", "r", 10), span("embeddings", {}, "e", "b", 12), span("POST /ask", {}, "r", None, 0)]
    assert og.trace_tree(spans) == ["POST /ask", "  retrieval", "    embeddings", "  chat"]


def test_token_totals_accepts_both_naming_styles():
    new = span("chat", {"anhti.feature": "chat", "gen_ai.usage.input_tokens": 10, "gen_ai.usage.output_tokens": 20})
    old = span("chat", {"anhti.feature": "chat", "gen_ai.usage.prompt_tokens": 5, "gen_ai.usage.completion_tokens": 7}, "b")
    other = span("chat", {"anhti.feature": "knowledge_assistant", "gen_ai.usage.input_tokens": 3, "gen_ai.usage.output_tokens": 4}, "c")
    plain = span("POST /ask", {"http.route": "/ask"}, "d")
    assert og.token_totals([new, old, other, plain], SNAPSHOT) == {"chat": (15, 27), "knowledge_assistant": (3, 4)}
