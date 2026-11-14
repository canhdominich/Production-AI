import io
import logging

import _kit  # noqa: F401
from conftest import World
from anhti_platform.safelog import get_logger, mask

message = "Goi 0912345678 hoac mail an.nguyen@example.com ve don at047838"
buf = io.StringIO()
handler = logging.StreamHandler(buf)
log = get_logger()
log.addHandler(handler)
World().chat("dp-02", message=message)
line = buf.getvalue().strip().splitlines()[-1]
import json
event = json.loads(line)
event["request_id"] = "<id>"
event["latency_ms"] = "<ms>"
print("log line of the service:")
print(json.dumps(event, sort_keys=True))
print("contains phone:", "0912345678" in line, "| contains email:", "example.com" in line, "| contains message:", "at047838" in line)
print()
print("a careless line that echoes upstream text:")
print("  raw   :", f"provider said: invalid prompt '{message}'")
print("  masked:", mask(f"provider said: invalid prompt '{message}'"))
