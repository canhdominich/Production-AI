import _kit  # noqa: F401
from conftest import World

w = World(primary_script=["server_error:500"])
w.chat("dp-02")
spans = sorted(w.telemetry.spans(), key=lambda s: s.start_time)
depth = {}
t0 = spans[0].start_time
for s in spans:
    d = 0 if s.parent is None else depth[s.parent.span_id] + 1
    depth[s.context.span_id] = d
    attrs = {k: v for k, v in s.attributes.items() if k in ("tenant_id", "provider", "attempt", "prompt_version")}
    print(f"{'  ' * d}{s.name:16} start +{(s.start_time - t0) / 1e6:6.2f} ms  {attrs}")
print("trace ids:", len({s.context.trace_id for s in spans}), "| spans:", len(spans))
