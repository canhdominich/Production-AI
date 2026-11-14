import logging
import re

import pytest

from anhti_platform.safelog import mask
from conftest import NOW, seed_spend


def test_every_call_writes_one_usage_event_with_cost_and_tenant(world):
    r = world.chat("dp-02")
    assert r.status_code == 200
    (e,) = world.store.events
    assert e["tenant_id"] == "br-dau-pho" and e["user_id"] == "dp-02" and e["feature"] == "chat"
    assert e["status"] == "ok" and e["prompt_version"] == "v1"
    assert e["prompt_tokens"] > 0 and e["output_tokens"] == 40 and e["cost_usd"] > 0
    assert e["cost_usd"] == pytest.approx(r.json()["cost_usd"])


def test_failed_call_is_recorded_with_zero_cost(make_world):
    w = make_world(["server_error:500"] * 5, ["timeout"] * 5)
    assert w.chat("dp-02").status_code == 503
    (e,) = w.store.events
    assert e["status"] != "ok" and e["cost_usd"] == 0 and e["attempts"] == 3


def test_cost_adds_up_per_tenant(world):
    for _ in range(3):
        world.chat("dp-02")
    world.chat("kc-02")
    mine = world.store.month_spend("br-dau-pho", "2026-11")
    assert mine == pytest.approx(sum(e["cost_usd"] for e in world.store.events if e["tenant_id"] == "br-dau-pho"))
    assert world.store.month_spend("br-khu-cong-nghiep", "2026-11") < mine


def test_soft_limit_downgrades_the_tier_and_says_so(world):
    seed_spend(world.store, "br-cau-go", 150 * 0.85)
    body = world.chat("cg-02", tier="large").json()
    assert body["model"] == "fake-small" and body["budget_state"] == "soft"


def test_below_the_soft_limit_the_requested_tier_is_kept(world):
    seed_spend(world.store, "br-cau-go", 10)
    body = world.chat("cg-03", tier="large").json()
    assert body["model"] == "fake-large" and body["budget_state"] == "ok"


def test_hard_limit_refuses_with_402_before_the_provider(world):
    seed_spend(world.store, "br-cau-go", 150.0)
    r = world.chat("cg-02")
    assert r.status_code == 402 and r.json()["error"]["code"] == "quota_exceeded"
    assert world.primary.calls == 0
    assert world.chat("dp-02").status_code == 200


def test_a_request_that_would_cross_the_budget_is_refused(world):
    seed_spend(world.store, "br-ben-song", 60.0 - 1e-9)
    assert world.chat("bs-01").status_code == 402


def test_only_the_current_month_counts_toward_the_quota(world):
    seed_spend(world.store, "br-cau-go", 500.0, ts=NOW - 40 * 86400)
    assert world.chat("cg-02").status_code == 200


def test_metrics_are_labelled_by_tenant_and_never_by_person(world):
    world.chat("dp-02")
    world.chat("kc-02")
    text = world.http.get("/metrics").text
    assert 'anhti_requests_total{feature="chat",status="ok",tenant="br-dau-pho"} 1.0' in text
    assert 'anhti_cost_usd_total{tenant="br-khu-cong-nghiep"}' in text
    assert "dp-02" not in text and "kc-02" not in text


def test_metric_cost_matches_the_usage_events(world):
    for u in ("dp-02", "kc-02", "dp-02"):
        world.chat(u)
    text = world.http.get("/metrics").text
    metric = float(re.search(r'anhti_cost_usd_total\{tenant="br-dau-pho"\} ([0-9.e-]+)', text).group(1))
    assert metric == pytest.approx(world.store.month_spend("br-dau-pho", "2026-11"))


def test_one_request_leaves_one_connected_trace(world):
    world.chat("dp-02")
    spans = {s.name: s for s in world.telemetry.spans()}
    assert set(spans) == {"api.request", "gateway.handle", "provider.call"}
    assert len({s.context.trace_id for s in spans.values()}) == 1
    assert spans["gateway.handle"].parent.span_id == spans["api.request"].context.span_id
    assert spans["provider.call"].parent.span_id == spans["gateway.handle"].context.span_id
    assert spans["gateway.handle"].attributes["tenant_id"] == "br-dau-pho"


def test_trace_shows_every_attempt_when_a_provider_fails(make_world):
    w = make_world(["server_error:500"])
    w.chat("dp-02")
    calls = [s for s in w.telemetry.spans() if s.name == "provider.call"]
    assert [(s.attributes["provider"], s.attributes["attempt"]) for s in calls] == [("primary", 1), ("secondary", 2)]


def test_logs_keep_ids_and_sizes_but_not_the_message_or_personal_data(world, caplog):
    secret = "Goi 0912345678 hoac mail an.nguyen@example.com ve don at047838"
    with caplog.at_level(logging.INFO, logger="anhti.platform"):
        r = world.chat("dp-02", message=secret)
    text = caplog.text
    assert r.status_code == 200
    assert r.json()["request_id"] in text and "br-dau-pho" in text and '"prompt_chars": %d' % len(secret) in text
    for leak in ("0912345678", "an.nguyen", "example.com", "at047838"):
        assert leak not in text


@pytest.mark.parametrize("raw", ["0912345678", "0912 345 678", "091.234.5678", "+84912345678", "84 912 345 678"])
def test_mask_covers_common_phone_formats(raw):
    assert mask(f"upstream rejected {raw} today") == "upstream rejected [PHONE] today"


def test_mask_covers_email_and_leaves_ordinary_numbers_alone():
    assert mask("mail a.b+c@mail.vn failed") == "mail [EMAIL] failed"
    assert mask("order 047838 took 1250 ms") == "order 047838 took 1250 ms"


def test_accidental_error_text_is_masked_by_the_logger_filter(caplog):
    from anhti_platform.safelog import get_logger
    with caplog.at_level(logging.INFO, logger="anhti.platform"):
        get_logger().info("provider echoed prompt: call 0987654321 or x@y.vn")
    assert "0987654321" not in caplog.text and "x@y.vn" not in caplog.text and "[PHONE]" in caplog.text
