import io

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

import safe_logging as sl


def make_system():
    api_buf, tools_buf = io.StringIO(), io.StringIO()
    api_log = sl.make_logger("lab.api", "api", api_buf)
    tools_log = sl.make_logger("lab.tools", "tools", tools_buf)

    tools = FastAPI()

    @tools.get("/orders/{order_id}")
    def get_order(order_id: str, request: Request):
        with sl.bind(request.headers.get("traceparent")):
            tools_log.info("order_lookup", extra={"order_id": order_id})
            return {"order_id": order_id, "status": "delivered"}

    tools_client = TestClient(tools)

    api = FastAPI()

    @api.post("/chat")
    def chat(body: dict, request: Request):
        with sl.bind(request.headers.get("traceparent")) as ids:
            api_log.info("request_received", extra={"tenant_id": body["tenant_id"], "prompt": body["text"]})
            api_log.info("user wrote: " + body["text"])
            api_log.info("provider_request", extra={"body": {"messages": [{"role": "user", "content": body["text"]}]}})
            order = tools_client.get(f"/orders/{body['order_id']}", headers={"traceparent": sl.current_traceparent()}).json()
            try:
                raise ValueError("cannot parse delivery note: " + body["text"])
            except ValueError:
                api_log.exception("note_parse_failed")
            return {"trace_id": ids["trace_id"], "order": order}

    return TestClient(api), api_buf, tools_buf
