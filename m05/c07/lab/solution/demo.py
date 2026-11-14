import json
import sys
import tempfile
from pathlib import Path

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace import SpanKind

import otel_genai as og

SNAPSHOT = {
    "attributes": ["gen_ai.operation.name", "gen_ai.provider.name", "gen_ai.request.model", "gen_ai.response.model", "gen_ai.request.max_tokens",
                   "gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens", "gen_ai.response.finish_reasons", "gen_ai.tool.name",
                   "gen_ai.tool.call.id", "gen_ai.input.messages", "gen_ai.output.messages", "gen_ai.retrieval.top_k", "gen_ai.agent.name"],
    "older_names": {"gen_ai.system": "gen_ai.provider.name", "gen_ai.usage.prompt_tokens": "gen_ai.usage.input_tokens",
                    "gen_ai.usage.completion_tokens": "gen_ai.usage.output_tokens"},
    "spans": {"chat": {"required": ["gen_ai.operation.name", "gen_ai.provider.name"]},
              "execute_tool": {"required": ["gen_ai.operation.name", "gen_ai.tool.name"]},
              "retrieval": {"required": ["gen_ai.operation.name"]},
              "invoke_agent": {"required": ["gen_ai.operation.name"]}},
}

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp()) / "traces.jsonl"
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(og.JsonlSpanExporter(path)))
tracer = provider.get_tracer("anhti.lab")


def chat(feature, model, tokens_in, tokens_out, finish):
    with tracer.start_as_current_span(og.span_name("chat", model), kind=SpanKind.CLIENT) as s:
        s.set_attributes(og.inference_attributes("fake", model, tokens_in, tokens_out, finish, 300))
        s.set_attribute("anhti.feature", feature)


with tracer.start_as_current_span("POST /chat", kind=SpanKind.SERVER):
    chat("chat", "fake-small", 13, 60, "stop")

with tracer.start_as_current_span("POST /ask", kind=SpanKind.SERVER):
    with tracer.start_as_current_span(og.span_name("retrieval"), kind=SpanKind.INTERNAL) as r:
        r.set_attributes({"gen_ai.operation.name": "retrieval", "gen_ai.retrieval.top_k": 3})
    chat("knowledge_assistant", "fake-medium", 120, 240, "length")

with tracer.start_as_current_span("POST /jobs", kind=SpanKind.SERVER):
    with tracer.start_as_current_span(og.span_name("invoke_agent", "weekly-report"), kind=SpanKind.INTERNAL) as a:
        a.set_attributes({"gen_ai.operation.name": "invoke_agent", "gen_ai.agent.name": "weekly-report"})
        chat("weekly_report_agent", "fake-large", 300, 900, "stop")
        with tracer.start_as_current_span(og.span_name("execute_tool", "get_order"), kind=SpanKind.INTERNAL) as t:
            t.set_attributes(og.tool_attributes("get_order", "call_0"))
        chat("weekly_report_agent", "fake-large", 320, 700, "stop")
provider.shutdown()

spans = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
print("\n".join(og.trace_tree(spans)))
problems = [(s["name"], p) for s in spans for p in og.validate_span(s, SNAPSHOT)]
print("validation problems:", len(problems))
print("token totals:", og.token_totals(spans, SNAPSHOT))
old = {"attributes": {"gen_ai.operation.name": "chat", "gen_ai.system": "fake", "gen_ai.usage.prompt_tokens": 13}}
print("older-style span:", og.validate_span(old, SNAPSHOT))
