import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Request
from opentelemetry import propagate, trace
from opentelemetry.trace import SpanKind

import _jsonlog
import _otel
import _redactkit

HERE = Path(__file__).resolve().parent
M04 = HERE.parents[2] / "m04" / "data"
OUT = Path(os.environ.get("TRACE_OUT", "/tmp/m05c08"))
PROPAGATE = os.environ.get("PROPAGATE", "1") == "1"
RAW_ATTRS = os.environ.get("RAW_ATTRS", "0") == "1"
PROVIDER = os.environ.get("PROVIDER_URL", "http://127.0.0.1:5680")
TOOLS = os.environ.get("TOOLS_URL", "http://127.0.0.1:5682")


def setup(service):
    OUT.mkdir(parents=True, exist_ok=True)
    tracer = _otel.make_tracer(service, _otel.JsonlExporter(OUT / f"{service}.spans.jsonl"))
    log = _jsonlog.make_logger(service, service, open(OUT / f"{service}.log.jsonl", "a", encoding="utf-8", buffering=1), ids=_otel.otel_ids)
    return tracer, log


def policy_paragraphs():
    text = (M04 / "policy.md").read_text(encoding="utf-8")
    return [p.strip() for p in text.split("\n\n") if p.startswith("**CS-")]


def tokens(text):
    return set(re.findall(r"\w+", _redactkit.fold(text).lower()))


def build_api():
    tracer, log = setup("api")
    app = FastAPI()
    docs = policy_paragraphs()
    client = httpx.Client(timeout=30)

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.post("/chat")
    async def chat(request: Request):
        body = await request.json()
        ctx = propagate.extract(dict(request.headers))
        with tracer.start_as_current_span("POST /chat", context=ctx, kind=SpanKind.SERVER) as span:
            span.set_attribute("tenant.id", body["tenant_id"])
            log.info("request_received", extra={"tenant_id": body["tenant_id"], "text_len": len(body["text"])})
            with tracer.start_as_current_span("retrieval") as r:
                query = tokens(body["text"])
                ranked = sorted(docs, key=lambda d: -len(query & tokens(d)))[:2]
                doc_ids = [d.split(".")[0].strip("*") for d in ranked]
                r.set_attribute("gen_ai.operation.name", "retrieval")
                r.set_attribute("gen_ai.retrieval.top_k", 2)
                r.set_attribute("retrieval.doc_ids", doc_ids)
                if RAW_ATTRS:
                    r.set_attribute("gen_ai.retrieval.query.text", body["text"])
                log.info("retrieval_done", extra={"doc_ids": doc_ids})
            context = "\n".join(ranked)
            with tracer.start_as_current_span("chat fake-medium", kind=SpanKind.CLIENT) as c:
                c.set_attribute("gen_ai.operation.name", "chat")
                c.set_attribute("gen_ai.provider.name", "fake")
                c.set_attribute("gen_ai.request.model", "fake-medium")
                headers = {"x-fake-request-id": body.get("request_id", "r-1"), "x-fake-output-tokens": "40"}
                propagate.inject(headers)
                resp = client.post(f"{PROVIDER}/v1/chat/completions", headers=headers, json={
                    "model": "fake-medium", "messages": [{"role": "system", "content": context}, {"role": "user", "content": body["text"]}], "max_tokens": 80})
                usage = resp.json()["usage"]
                c.set_attribute("gen_ai.usage.input_tokens", usage["prompt_tokens"])
                c.set_attribute("gen_ai.usage.output_tokens", usage["completion_tokens"])
                log.info("provider_done", extra={"status": resp.status_code, "output_tokens": usage["completion_tokens"]})
            match = re.search(r"AT\d{6}", body["text"])
            order = None
            if match:
                with tracer.start_as_current_span("execute_tool get_order", kind=SpanKind.CLIENT) as t:
                    t.set_attribute("gen_ai.operation.name", "execute_tool")
                    t.set_attribute("gen_ai.tool.name", "get_order")
                    headers = {}
                    if PROPAGATE:
                        propagate.inject(headers)
                    order = client.get(f"{TOOLS}/orders/{match.group(0)}", headers=headers).json()
                    log.info("tool_done", extra={"tool": "get_order", "found": order.get("found")})
            ids = _otel.otel_ids()
            return {"trace_id": ids["trace_id"], "doc_ids": doc_ids, "order": order}

    return app


def build_tools():
    tracer, log = setup("tools")
    app = FastAPI()
    with open(M04 / "orders.csv", encoding="utf-8", newline="") as f:
        orders = {r["order_id"]: r for r in csv.DictReader(f)}

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/orders/{order_id}")
    def get_order(order_id: str, request: Request):
        ctx = propagate.extract(dict(request.headers))
        with tracer.start_as_current_span("GET /orders/{order_id}", context=ctx, kind=SpanKind.SERVER) as span:
            row = orders.get(order_id)
            span.set_attribute("order.found", row is not None)
            log.info("order_lookup", extra={"order_id": order_id, "found": row is not None})
            return {"order_id": order_id, "found": row is not None, "status": row["status"] if row else None}

    return app


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("service", choices=["api", "tools"])
    ap.add_argument("--port", type=int, required=True)
    a = ap.parse_args()
    uvicorn.run(build_api() if a.service == "api" else build_tools(), host="127.0.0.1", port=a.port, log_level="warning")
