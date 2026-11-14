import httpx

import _harness as h

CLIENT_TRACE, CLIENT_SPAN = "4bf92f3577b34da6a3ce929d0e0e4736", "00f067aa0ba902b7"
TEXT = "Đơn AT310007 giao trễ, mình cần biết đơn đang ở đâu"


def trace_health(spans, browser_span):
    ids = {s["span_id"] for s in spans}
    roots = [s for s in spans if s["parent_id"] not in ids or s["parent_id"] == browser_span]
    return len({s["trace_id"] for s in spans}), roots


def run(propagate):
    with h.stack(PROPAGATE=int(propagate)):
        httpx.post(f"http://127.0.0.1:{h.PORTS['api']}/chat", json={"tenant_id": "br-cau-go", "text": TEXT, "request_id": "demo-2"},
                   headers={"traceparent": f"00-{CLIENT_TRACE}-{CLIENT_SPAN}-01"}, timeout=30)
        return h.load_spans(), h.load_logs()


for label, flag in (("tool call forwards the header", True), ("tool call forgets the header", False)):
    spans, logs = run(flag)
    n_traces, roots = trace_health(spans, CLIENT_SPAN)
    print(f"{label}: trace ids {n_traces}, root spans {len(roots)} (healthy is 1 and 1)")
    print("   tool log trace_id equals the browser trace id:", logs["tools"][0]["trace_id"] == CLIENT_TRACE)
    if len(roots) > 1:
        extra = next(s for s in roots if s["service"] == "tools")
        print("   second root:", extra["name"], "from", extra["service"], "with parent_id", extra["parent_id"])
