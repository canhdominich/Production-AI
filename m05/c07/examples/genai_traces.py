import json

from _genai import ObservedGateway, PolicyIndex, make_tracer, read_spans, traced_agent, traced_chat, traced_rag, tree_lines, validate_span
from _support import DATA, provider
from gateway_core import GatewayRequest, ProviderClient

OUT = DATA / "traces_demo.jsonl"
tracer, tp = make_tracer(OUT)
index = PolicyIndex()
Q = "Đơn standard trễ 70 phút thì được hoàn bao nhiêu phần trăm phí vận chuyển?"

with provider(5673, time_scale=0.02) as url:
    gw = ObservedGateway([ProviderClient("fake", url)])
    traced_chat(tracer, gw, GatewayRequest("br-cau-go", "chat", [{"role": "user", "content": "Đơn A-1001 đến chưa?"}], "small", "cskh_agent", "chat-0001", output_tokens=60))
    traced_rag(tracer, gw, index, GatewayRequest("br-dau-pho", "knowledge_assistant", [], "medium", "branch_lead", "rag-0001", output_tokens=120), Q)
    traced_agent(tracer, gw, GatewayRequest("br-dau-pho", "weekly_report_agent", [{"role": "user", "content": "Weekly report"}], "large", "branch_manager", "job-0001"))
tp.shutdown()

spans = read_spans(OUT)
chat = next(s for s in spans if s["name"].startswith("chat ") and s["attributes"].get("anhti.feature") == "chat")
shown = {k: v for k, v in chat["attributes"].items()}
print("One chat span, attributes as exported:")
print(json.dumps({"name": chat["name"], "kind": chat["kind"], "status": chat["status"], "attributes": shown}, ensure_ascii=False, indent=1))
for trace_id in dict.fromkeys(s["trace_id"] for s in spans):
    part = [s for s in spans if s["trace_id"] == trace_id]
    root = next(s for s in part if s["parent_span_id"] is None)
    print(f"\ntrace {trace_id[:8]}: {len(part)} spans")
    print("\n".join(tree_lines(part)))
problems = [(s["name"], p) for s in spans for p in validate_span(s)]
print(f"\nspans {len(spans)}, validation problems {len(problems)}")
