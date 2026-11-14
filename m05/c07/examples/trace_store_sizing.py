import json
import statistics

from _genai import ObservedGateway, make_tracer, read_spans, traced_chat
from _support import DATA, provider
from gateway_core import GatewayRequest, ProviderClient

spans = read_spans(DATA / "traces_store.jsonl")
sizes = [len(json.dumps(s, ensure_ascii=False).encode()) for s in spans]
per_span = statistics.mean(sizes)
MSG = "Shipper gọi số 0901234567 nhưng tôi đang ở số 12 đường Lê Lợi, quận Cầu Gỗ. Đơn A-1001 giao trễ gần một tiếng, tôi muốn được hoàn phí."
line = {}
with provider(5677, time_scale=0.02) as url:
    gw = ObservedGateway([ProviderClient("fake", url)])
    for capture in (False, True):
        path = DATA / "size_probe.jsonl"
        tracer, tp = make_tracer(path)
        traced_chat(tracer, gw, GatewayRequest("br-cau-go", "chat", [{"role": "user", "content": MSG}], "small", "cskh_agent", "probe", output_tokens=120), capture_content=capture)
        tp.shutdown()
        line[capture] = len(path.read_text(encoding="utf-8").strip().encode())
path.unlink()
content_extra = line[True] - line[False]

SPANS_PER_REQUEST = {"chat": 2, "knowledge_assistant": 5, "weekly_report_agent": 12}
SHARE = {"chat": 0.70, "knowledge_assistant": 0.27, "weekly_report_agent": 0.03}
REQUESTS_PER_DAY = 20000
RETENTION_DAYS = 30

avg_spans = sum(SPANS_PER_REQUEST[f] * SHARE[f] for f in SHARE)
print(f"measured: {per_span:.0f} bytes per span without content (mean of {len(spans)} spans); with prompt and answer about +{content_extra} bytes")
print(f"assumed traffic: {REQUESTS_PER_DAY} requests per day, mix 70/27/3, {avg_spans:.2f} spans per request on average, keep {RETENTION_DAYS} days")
print(f"{'policy':58}{'GB stored':>10}")
for name, keep_ok, extra in [("keep every trace, no content", 1.0, 0), ("keep every trace, with content", 1.0, content_extra), ("keep 10% of ok traces + all slow or failed (assume 8%)", 0.10 * 0.92 + 0.08, 0), ("same sampling, with content", 0.10 * 0.92 + 0.08, content_extra)]:
    total = REQUESTS_PER_DAY * RETENTION_DAYS * avg_spans * keep_ok * (per_span + extra)
    print(f"{name:58}{total / 1e9:>10.2f}")
