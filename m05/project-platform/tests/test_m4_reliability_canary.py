import random

import pytest

from anhti_platform.base import GatewayRequest
from anhti_platform.canary import CanaryRouter, RollbackController, bucket
from anhti_platform.gateway import AllProvidersFailed, CircuitBreaker, PlatformGateway, QuotaExceeded
from anhti_platform.limits import SlidingWindowLimiter
from anhti_platform.usage import MemoryUsageStore
from conftest import Clock, ScriptedProvider


@pytest.mark.parametrize("fault", ["server_error:500", "rate_limit:429", "timeout", "connection"])
def test_retryable_failure_on_the_primary_is_served_by_the_secondary(make_world, fault):
    w = make_world([fault], [])
    r = w.chat("dp-02")
    body = r.json()
    assert r.status_code == 200
    assert (body["provider"], body["fallback_used"], body["attempts"]) == ("secondary", True, 2)
    assert w.store.events[-1]["fallback_used"] is True


def test_a_healthy_primary_is_not_marked_as_fallback(world):
    body = world.chat("dp-02").json()
    assert (body["provider"], body["fallback_used"], body["attempts"]) == ("primary", False, 1)
    assert world.secondary.calls == 0


def test_a_bad_request_is_not_retried_on_another_provider(make_world):
    w = make_world(["bad_request:400"], [])
    assert w.chat("dp-02").status_code == 503
    assert w.secondary.calls == 0


def test_all_providers_failing_gives_503_with_retry_hint(make_world):
    w = make_world(["server_error:500"] * 3, ["timeout"] * 3)
    r = w.chat("dp-02")
    assert r.status_code == 503 and r.headers["retry-after"] == "5"
    assert r.json()["error"]["code"] == "provider_unavailable"
    assert w.primary.calls + w.secondary.calls == 3


def test_backoff_is_capped_and_honours_retry_after(make_world):
    w = make_world(["rate_limit:429"], ["server_error:500"])
    w.chat("dp-02")
    assert len(w.sleeps) == 2
    assert all(0 <= s <= 2.0 for s in w.sleeps)
    assert w.sleeps[0] >= 1.5


def test_no_sleep_after_the_last_attempt(make_world):
    w = make_world(["server_error:500"] * 3, ["server_error:500"] * 3)
    w.chat("dp-02")
    assert len(w.sleeps) == 2


def make_gateway(primary, secondary, **kw):
    mono = Clock(0.0)
    gw = PlatformGateway([primary, secondary], MemoryUsageStore(), SlidingWindowLimiter(), clock=Clock(), sleep=lambda s: None,
                         mono=mono, **kw)
    return gw, mono


def request(i=0):
    return GatewayRequest("br-dau-pho", "chat", [{"role": "user", "content": f"q{i}"}], "medium", "branch_lead", request_id=f"r{i}")


def test_breaker_opens_after_repeated_failures_and_stops_calling_the_primary():
    primary = ScriptedProvider("primary", ["server_error:500"] * 50)
    gw, _ = make_gateway(primary, ScriptedProvider("secondary"))
    for i in range(3):
        assert gw.handle(request(i)).record.provider == "secondary"
    assert gw.breakers["primary"].state == "open"
    calls = primary.calls
    for i in range(3, 10):
        gw.handle(request(i))
    assert primary.calls == calls


def test_breaker_half_open_probe_closes_it_again_when_the_primary_recovers():
    primary = ScriptedProvider("primary", ["server_error:500"] * 3)
    gw, mono = make_gateway(primary, ScriptedProvider("secondary"))
    for i in range(3):
        gw.handle(request(i))
    mono.advance(31)
    assert gw.breakers["primary"].state == "half_open"
    assert gw.handle(request(9)).record.provider == "primary"
    assert gw.breakers["primary"].state == "closed"


def test_breaker_half_open_allows_one_probe_only():
    b = CircuitBreaker(2, 10.0, Clock(0.0))
    b.failure(); b.failure()
    assert not b.allow()
    b.clock.advance(11)
    assert b.allow() and not b.allow()
    b.failure()
    assert b.state == "open"


def test_when_every_breaker_is_open_the_request_fails_fast():
    primary, secondary = ScriptedProvider("primary", ["server_error:500"] * 9), ScriptedProvider("secondary", ["server_error:500"] * 9)
    gw, _ = make_gateway(primary, secondary)
    for i in range(3):
        with pytest.raises(AllProvidersFailed):
            gw.handle(request(i))
    before = primary.calls + secondary.calls
    with pytest.raises(AllProvidersFailed):
        gw.handle(request(99))
    assert primary.calls + secondary.calls == before


def test_chaos_mix_never_surfaces_a_provider_fault_to_the_client():
    rnd = random.Random(15)
    faults = ["server_error:500", "rate_limit:429", "timeout"]
    primary = ScriptedProvider("primary", [rnd.choice(faults) if rnd.random() < 0.3 else "ok" for _ in range(400)])
    gw, _ = make_gateway(primary, ScriptedProvider("secondary"), failure_threshold=1000)
    ok = []
    for i in range(200):
        gw.clock.advance(1)
        ok.append(gw.handle(request(i)).record)
    assert all(r.status == "ok" for r in ok)
    share = sum(r.fallback_used for r in ok) / len(ok)
    assert 0.1 < share < 0.4


def test_quota_error_type_is_not_retried_on_another_provider():
    gw, _ = make_gateway(ScriptedProvider("primary"), ScriptedProvider("secondary"))
    gw.store.add({"request_id": "s", "ts": Clock()(), "tenant_id": "br-ben-song", "user_id": "x", "feature": "chat", "model": "m", "provider": "p",
                  "status": "ok", "prompt_tokens": 0, "output_tokens": 0, "cost_usd": 60.0, "latency_ms": 1, "attempts": 1,
                  "fallback_used": False, "prompt_version": "v1"})
    req = request(1)
    req.tenant_id = "br-ben-song"
    with pytest.raises(QuotaExceeded):
        gw.handle(req)


def test_canary_split_is_stable_per_user_and_close_to_the_target():
    router = CanaryRouter(percent=10)
    users = [f"user-{i}" for i in range(2000)]
    first = [router.route(u) for u in users]
    assert first == [router.route(u) for u in users]
    assert 0.07 < first.count("v2") / len(users) < 0.13
    assert 0 <= bucket("dp-01", "x") < 100


def test_canary_at_zero_percent_sends_everyone_to_stable():
    router = CanaryRouter(percent=0)
    assert {router.route(f"u{i}") for i in range(500)} == {"v1"}


def feed(ctl, stable, canary, n=40):
    for _ in range(n):
        ctl.observe("v1", stable)
        ctl.observe("v2", canary)


def test_controller_rolls_back_after_two_bad_windows_in_a_row():
    router = CanaryRouter(percent=10)
    ctl = RollbackController(router, min_samples=30)
    feed(ctl, 0.9, 0.7)
    assert ctl.check() == "running"
    feed(ctl, 0.9, 0.7)
    assert ctl.check() == "rolled_back"
    assert router.percent == 0
    assert {router.route(f"u{i}") for i in range(200)} == {"v1"}


def test_one_noisy_window_does_not_trigger_a_rollback():
    ctl = RollbackController(CanaryRouter(percent=10), min_samples=30)
    feed(ctl, 0.9, 0.7)
    ctl.check()
    feed(ctl, 0.9, 0.9)
    assert ctl.check() == "running"
    feed(ctl, 0.9, 0.7)
    assert ctl.check() == "running"


def test_controller_waits_for_enough_samples():
    ctl = RollbackController(CanaryRouter(percent=10), min_samples=30)
    feed(ctl, 0.9, 0.1, n=10)
    assert ctl.check() == "collecting"


def test_controller_promotes_after_enough_healthy_windows():
    router = CanaryRouter(percent=10)
    ctl = RollbackController(router, min_samples=30, promote_after=3)
    for _ in range(3):
        feed(ctl, 0.9, 0.91)
        state = ctl.check()
    assert state == "promoted" and router.percent == 100


def test_decisions_are_final_until_someone_restarts_the_release():
    router = CanaryRouter(percent=10)
    ctl = RollbackController(router, min_samples=30, strikes=1)
    feed(ctl, 0.9, 0.5)
    assert ctl.check() == "rolled_back"
    feed(ctl, 0.9, 0.95)
    assert ctl.check() == "rolled_back" and router.percent == 0


def test_bad_quality_reports_roll_the_live_service_back_to_the_stable_prompt(make_world):
    w = make_world()
    w.app.state.router.percent = 100
    assert w.chat("dp-02").json()["prompt_version"] == "v2"
    state = ""
    for _ in range(2):
        for _ in range(30):
            w.app.state.report_quality("v1", 0.9)
            state = w.app.state.report_quality("v2", 0.6)
    assert state == "rolled_back"
    assert w.chat("dp-02").json()["prompt_version"] == "v1"
    assert 'anhti_quality_score{prompt_version="v2"}' in w.http.get("/metrics").text
