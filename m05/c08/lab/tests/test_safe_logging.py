import io
import json
import logging
import re

import pytest

import safe_logging as sl
from lab_app import make_system

BROWSER_TRACE, BROWSER_SPAN = "4bf92f3577b34da6a3ce929d0e0e4736", "00f067aa0ba902b7"
BROWSER_HEADER = f"00-{BROWSER_TRACE}-{BROWSER_SPAN}-01"

PHONES = ["0901234567", "0901 234 567", "090 123 4567", "0901.234.567", "0901-234-567", "+84901234567", "+84 901 234 567", "(+84) 901234567", "84901234567", "0587654321"]
ADDRESSES = [
    "số 12 ngõ 5 đường Hoa Sen, phường Cầu Gỗ, quận Đầu Phố",
    "12/3 Trăng Non, P. Xóm Vui, Q. Bến Sông",
    "hẻm 25 đường Sao Mai, khu phố 3, phường Chợ Mới",
    "chung cư Xóm Vui tòa B căn 1203",
    "so 7 ngo 14 duong che xanh, phuong cau go, quan dau pho",
    "số 88 đường Cá Rô, quận Khu Công Nghiệp",
]
NOT_PHONES = ["thu hộ 1.500.000đ", "mã 7084123456789", "doanh thu 10.084.123.456đ", "đơn AT084123456", "ngày 08/04/2026 lúc 17:30", "TRK0912345678"]
NOT_ADDRESSES = ["Nhà mình gần Cầu Gỗ, ship nhanh giúp mình", "Đơn AT310007 nặng 12kg, 3 thùng", "giao trước 17:30 ngày 10/11/2026", "số 5 thùng hàng"]


def test_new_traceparent_is_valid_and_random():
    a, b = sl.new_traceparent(), sl.new_traceparent()
    assert re.fullmatch(r"00-[0-9a-f]{32}-[0-9a-f]{16}-01", a)
    assert a != b
    assert sl.new_traceparent(sampled=False).endswith("-00")


def test_parse_valid_header():
    assert sl.parse_traceparent(BROWSER_HEADER) == {"version": "00", "trace_id": BROWSER_TRACE, "parent_id": BROWSER_SPAN, "flags": "01"}


@pytest.mark.parametrize("bad", [
    None, "", "garbage", "00-" + "0" * 32 + f"-{BROWSER_SPAN}-01", f"00-{BROWSER_TRACE}-" + "0" * 16 + "-01",
    BROWSER_HEADER.upper(), f"00-{BROWSER_TRACE[:20]}-{BROWSER_SPAN}-01", f"ff-{BROWSER_TRACE}-{BROWSER_SPAN}-01", BROWSER_HEADER + "-extra",
])
def test_parse_rejects_invalid(bad):
    assert sl.parse_traceparent(bad) is None


def test_child_keeps_trace_and_flags_but_changes_span():
    child = sl.parse_traceparent(sl.child_traceparent(f"00-{BROWSER_TRACE}-{BROWSER_SPAN}-00"))
    assert child["trace_id"] == BROWSER_TRACE and child["flags"] == "00"
    assert child["parent_id"] != BROWSER_SPAN and len(child["parent_id"]) == 16


def test_child_of_invalid_header_starts_a_new_trace():
    assert sl.parse_traceparent(sl.child_traceparent("nonsense")) is not None
    assert sl.parse_traceparent(sl.child_traceparent(None))["trace_id"] != BROWSER_TRACE


@pytest.mark.parametrize("phone", PHONES)
def test_phone_formats_are_masked(phone):
    assert sl.redact_phone(f"gọi {phone} nhé") == "gọi [phone] nhé"


def test_two_phones_in_one_text():
    assert sl.redact_phone("0901234567 hoặc +84 912 345 678") == "[phone] hoặc [phone]"


@pytest.mark.parametrize("text", NOT_PHONES)
def test_numbers_that_are_not_phones_survive(text):
    assert sl.redact_phone(text) == text


@pytest.mark.parametrize("address", ADDRESSES)
def test_address_is_masked(address):
    assert sl.redact_address(f"giao tới {address} giúp mình") == "giao tới [address] giúp mình"


@pytest.mark.parametrize("text", NOT_ADDRESSES)
def test_text_without_address_survives(text):
    assert sl.redact_address(text) == text


def test_redact_text_handles_phone_before_address():
    assert sl.redact_text("số 0901234567 và số 12 ngõ 5 đường Hoa Sen") == "số [phone] và [address]"


def test_redact_value_walks_containers_and_does_not_mutate():
    original = {"body": {"messages": [{"content": "gọi 0901234567"}]}, "tags": ("a", "gọi 0912345678"), "n": 3, "ok": True, "none": None}
    clean = sl.redact_value(original)
    assert clean["body"]["messages"][0]["content"] == "gọi [phone]"
    assert clean["tags"] == ["a", "gọi [phone]"]
    assert (clean["n"], clean["ok"], clean["none"]) == (3, True, None)
    assert original["body"]["messages"][0]["content"] == "gọi 0901234567"


def test_redact_value_denies_keys_and_keeps_own_keys():
    clean = sl.redact_value({"prompt": "anything", "phone": "x", "authorization": "Bearer abc", "request_id": "0901234567", "tenant_id": "br-cau-go"})
    assert clean["prompt"] == clean["phone"] == clean["authorization"] == "[removed]"
    assert clean["request_id"] == "0901234567"
    assert clean["tenant_id"] == "br-cau-go"


def make_log():
    buf = io.StringIO()
    return sl.make_logger("test.logger", "api", buf), buf


def test_formatter_writes_one_json_line_with_fields():
    log, buf = make_log()
    log.info("provider_done", extra={"tenant_id": "br-cau-go", "latency_ms": 420})
    lines = buf.getvalue().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["event"] == "provider_done" and row["level"] == "INFO" and row["service"] == "api"
    assert row["tenant_id"] == "br-cau-go" and row["latency_ms"] == 420
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT.*(\+00:00|Z)", row["ts"])
    assert "trace_id" not in row


def test_formatter_adds_ids_only_inside_bind():
    log, buf = make_log()
    with sl.bind(BROWSER_HEADER) as ids:
        log.info("inside")
        inside_span = ids["span_id"]
    log.info("outside")
    inside, outside = [json.loads(x) for x in buf.getvalue().splitlines()]
    assert inside["trace_id"] == BROWSER_TRACE and inside["span_id"] == inside_span != BROWSER_SPAN
    assert "trace_id" not in outside


def test_formatter_masks_message_extra_and_exception():
    log, buf = make_log()
    log.info("customer said: gọi 0901 234 567, giao số 12 ngõ 5 đường Hoa Sen")
    log.info("provider_request", extra={"body": {"messages": [{"content": "ở 12/3 Trăng Non, P. Xóm Vui"}]}, "prompt": "raw text"})
    try:
        raise ValueError("cannot parse note from 0912 345 678")
    except ValueError:
        log.exception("note_failed")
    out = buf.getvalue()
    for secret in ["0901 234 567", "ngõ 5 đường Hoa Sen", "Trăng Non", "0912 345 678", "raw text"]:
        assert secret not in out
    rows = [json.loads(x) for x in out.splitlines()]
    assert "[phone]" in rows[0]["event"] and "[address]" in rows[0]["event"]
    assert rows[1]["prompt"] == "[removed]"
    assert "ValueError" in rows[2]["exc"] and "[phone]" in rows[2]["exc"]


def test_formatter_survives_objects_json_cannot_encode():
    log, buf = make_log()
    log.info("odd", extra={"thing": {1, 2}, "obj": object})
    assert json.loads(buf.getvalue())["event"] == "odd"


def test_find_leaks():
    lines = ['{"event": "gọi 0901 234 567"}', '{"event": "ok"}', '{"event": "contact 0912.345.678"}']
    assert sl.find_leaks(lines, ["0901 234 567", "0912345678", "0987654321", "Hoa Sen"]) == ["0901 234 567", "0912345678"]
    assert sl.find_leaks([], ["0901234567"]) == []


TEXT = "Đơn AT310007 giao trễ, mình ở số 12 ngõ 5 đường Hoa Sen, phường Cầu Gỗ, gọi 0901 234 567 nhé"
SECRETS = ["0901 234 567", "số 12 ngõ 5 đường Hoa Sen, phường Cầu Gỗ"]


def test_one_trace_id_across_two_services_and_no_personal_data():
    client, api_buf, tools_buf = make_system()
    r = client.post("/chat", json={"tenant_id": "br-cau-go", "text": TEXT, "order_id": "AT310007"}, headers={"traceparent": BROWSER_HEADER})
    assert r.status_code == 200 and r.json()["trace_id"] == BROWSER_TRACE
    api_rows = [json.loads(x) for x in api_buf.getvalue().splitlines()]
    tools_rows = [json.loads(x) for x in tools_buf.getvalue().splitlines()]
    assert len(api_rows) >= 4 and len(tools_rows) == 1
    assert {row["trace_id"] for row in api_rows + tools_rows} == {BROWSER_TRACE}
    assert tools_rows[0]["span_id"] != api_rows[0]["span_id"]
    assert sl.find_leaks(api_buf.getvalue().splitlines() + tools_buf.getvalue().splitlines(), SECRETS) == []


def test_request_without_header_still_gets_one_trace_id_everywhere():
    client, api_buf, tools_buf = make_system()
    r = client.post("/chat", json={"tenant_id": "br-cau-go", "text": TEXT, "order_id": "AT310007"})
    ids = {json.loads(x)["trace_id"] for x in api_buf.getvalue().splitlines() + tools_buf.getvalue().splitlines()}
    assert ids == {r.json()["trace_id"]} and r.json()["trace_id"] != BROWSER_TRACE


def test_two_requests_do_not_share_ids():
    client, api_buf, _ = make_system()
    a = client.post("/chat", json={"tenant_id": "t", "text": "x", "order_id": "AT1"}).json()["trace_id"]
    b = client.post("/chat", json={"tenant_id": "t", "text": "y", "order_id": "AT2"}).json()["trace_id"]
    assert a != b


def test_replay_of_many_messages_leaves_no_personal_data():
    client, api_buf, tools_buf = make_system()
    secrets_ = []
    for i, phone in enumerate(PHONES):
        address = ADDRESSES[i % len(ADDRESSES)]
        client.post("/chat", json={"tenant_id": "br-cau-go", "text": f"Đơn AT3100{i:02d} gọi {phone}, nhận tại {address}", "order_id": f"AT3100{i:02d}"})
        secrets_ += [phone, address]
    assert sl.find_leaks(api_buf.getvalue().splitlines() + tools_buf.getvalue().splitlines(), secrets_) == []
