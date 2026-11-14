import io
import json
import logging
import re

import _jsonlog

EVENTS = [
    ("br-cau-go", "chat", "ok", 420), ("br-cau-go", "chat", "timeout", 2310), ("br-dau-pho", "knowledge_assistant", "ok", 1180),
    ("br-cau-go", "knowledge_assistant", "timeout", 1890), ("br-ben-song", "chat", "rate_limit", 35), ("br-cau-go", "chat", "timeout", 3050),
    ("br-dau-pho", "chat", "timeout", 2750), ("br-cau-go", "weekly_report_agent", "timeout", 9120), ("br-cau-go", "chat", "ok", 510),
]

text_io, json_io = io.StringIO(), io.StringIO()
text_log = logging.getLogger("text")
text_log.setLevel(logging.INFO)
h = logging.StreamHandler(text_io)
h.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
text_log.addHandler(h)
json_log = _jsonlog.make_logger("json", "gateway", json_io)

for i, (tenant, feature, status, ms) in enumerate(EVENTS):
    if i % 3 == 2:
        text_log.warning("provider call to %s for %s ended with %s after %d ms", feature, tenant, status, ms)
    else:
        text_log.warning("gateway call failed tenant=%s feature=%s status=%s latency=%dms", tenant, feature, status, ms)
    json_log.warning("provider_call_finished", extra={"tenant_id": tenant, "feature": feature, "status": status, "latency_ms": ms})

pattern = re.compile(r"tenant=br-cau-go .* status=timeout latency=(\d+)ms")
rows = [json.loads(line) for line in json_io.getvalue().splitlines()]
by_regex = [m for line in text_io.getvalue().splitlines() if (m := pattern.search(line)) and int(m.group(1)) > 1500]
by_field = [r for r in rows if r["tenant_id"] == "br-cau-go" and r["status"] == "timeout" and r["latency_ms"] > 1500]

print("one text line :", text_io.getvalue().splitlines()[0])
print("one json line :", {k: v for k, v in rows[0].items() if k != "ts"})
print("regex on text finds", len(by_regex), "slow timeouts of br-cau-go")
print("filter on json finds", len(by_field), "slow timeouts of br-cau-go")
