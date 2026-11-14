import re

from opentelemetry import propagate, trace

GOOD = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
SHAPE = re.compile(r"^[0-9a-f]{2}-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$")

CASES = {
    "valid": GOOD,
    "all-zero trace id": "00-00000000000000000000000000000000-00f067aa0ba902b7-01",
    "uppercase hex": "00-4BF92F3577B34DA6A3CE929D0E0E4736-00f067aa0ba902b7-01",
    "trace id too short": "00-4bf92f3577b34da6-00f067aa0ba902b7-01",
    "all-zero parent id": "00-4bf92f3577b34da6a3ce929d0e0e4736-0000000000000000-01",
}

print("fields of a valid header:", dict(zip(("version", "trace-id", "parent-id", "trace-flags"), GOOD.split("-"))))
for name, header in CASES.items():
    ctx = propagate.extract({"traceparent": header})
    sc = trace.get_current_span(ctx).get_span_context()
    print(f"{name:<20} shape ok: {bool(SHAPE.match(header))!s:<5} accepted by OpenTelemetry: {sc.is_valid}")

tracer = trace.get_tracer("demo")
ctx = propagate.extract({"traceparent": GOOD})
with tracer.start_as_current_span("child", context=ctx) as span:
    carrier = {}
    propagate.inject(carrier)
    print("a process with no SDK still forwards the same header:", carrier.get("traceparent", "no header"))
