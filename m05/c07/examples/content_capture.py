import json
import re

from _genai import ObservedGateway, make_tracer, read_spans, validate_span
from _support import DATA, provider
from gateway_core import GatewayRequest, ProviderClient

PHONE = re.compile(r"0\d{9}")
MSG = "Shipper gọi số 0901234567 nhưng tôi đang ở số 12 đường Lê Lợi, quận Cầu Gỗ. Đơn A-1001 giao trễ gần một tiếng, tôi muốn được hoàn phí."

with provider(5674, time_scale=0.02) as url:
    gw = ObservedGateway([ProviderClient("fake", url)])
    for capture in (False, True):
        path = DATA / f"capture_{'on' if capture else 'off'}.jsonl"
        tracer, tp = make_tracer(path)
        from _genai import traced_chat
        traced_chat(tracer, gw, GatewayRequest("br-cau-go", "chat", [{"role": "user", "content": MSG}], "small", "cskh_agent", "cap-1", output_tokens=80), capture_content=capture)
        tp.shutdown()
        line = path.read_text(encoding="utf-8").strip()
        span = read_spans(path)[0]
        found = bool(PHONE.search(line))
        problems = validate_span(span, allow_content=capture)
        print(f"content capture {'ON ' if capture else 'OFF'}: {len(line):5} bytes per span, phone number inside the stored span: {found}, attributes {len(span['attributes'])}, validator {'ok' if not problems else problems}")
