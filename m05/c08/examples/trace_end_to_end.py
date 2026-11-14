import httpx

import _harness as h

CLIENT_TRACE, CLIENT_SPAN = "4bf92f3577b34da6a3ce929d0e0e4736", "00f067aa0ba902b7"
TEXT = "Đơn AT310007 giao trễ, mình ở số 12 ngõ 5 đường Hoa Sen, phường Cầu Gỗ, gọi 0901 234 567 nhé"

with h.stack() as out:
    r = httpx.post(f"http://127.0.0.1:{h.PORTS['api']}/chat", json={"tenant_id": "br-cau-go", "text": TEXT, "request_id": "demo-1"},
                   headers={"traceparent": f"00-{CLIENT_TRACE}-{CLIENT_SPAN}-01"}, timeout=30)
    spans, logs = h.load_spans(), h.load_logs()

print("client sent traceparent:", f"00-{CLIENT_TRACE[:8]}...-{CLIENT_SPAN}-01")
print("API answered with trace_id:", r.json()["trace_id"][:8] + "...", "| order found:", r.json()["order"]["found"])
print(f"spans: {len(spans)} from {len({s['service'] for s in spans})} processes, distinct trace ids: {len({s['trace_id'] for s in spans})}")
h.print_tree(spans, root_parent=CLIENT_SPAN)
root = next(s for s in spans if s["name"] == "POST /chat")
print("root span is a child of the browser span:", root["parent_id"] == CLIENT_SPAN)
for service, lines in logs.items():
    print(f"log lines from {service:<5}: {len(lines)}, with the same trace_id: {sum(l.get('trace_id') == CLIENT_TRACE for l in lines)}")
print("tool log line:", {k: v for k, v in logs["tools"][0].items() if k not in ("ts", "span_id", "trace_id")})
