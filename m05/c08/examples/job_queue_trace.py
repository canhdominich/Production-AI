import json
import threading
import time

from opentelemetry import propagate
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import _harness as h

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
tracer = provider.get_tracer("demo")


def enqueue(r, report, carry):
    with tracer.start_as_current_span("POST /reports") as span:
        payload = {"report": report}
        if carry:
            carrier = {}
            propagate.inject(carrier)
            payload["traceparent"] = carrier["traceparent"]
        r.lpush("jobs", json.dumps(payload))


def worker(r):
    _, raw = r.brpop("jobs", timeout=5)
    job = json.loads(raw)
    time.sleep(0.2)
    ctx = propagate.extract({"traceparent": job["traceparent"]}) if "traceparent" in job else None
    with tracer.start_as_current_span("run weekly_report", context=ctx):
        pass


with h.redis_server(h.PORTS["redis"]) as r:
    for carry in (False, True):
        exporter.clear()
        t = threading.Thread(target=worker, args=(r,))
        t.start()
        enqueue(r, "week-45", carry)
        t.join()
        spans = exporter.get_finished_spans()
        api, job = next(s for s in spans if s.name == "POST /reports"), next(s for s in spans if s.name == "run weekly_report")
        print(f"traceparent stored in the job payload: {carry!s:<5} trace ids: {len({s.context.trace_id for s in spans})}, "
              f"worker span is a child of the API span: {job.parent is not None and job.parent.span_id == api.context.span_id}")
