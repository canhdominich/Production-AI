import random

import pytest

from reliability import (AllProvidersFailed, CircuitBreaker, ProviderFailure, ResilientCaller, backoff_delay, budget_status,
                         compute_slis, downtime_minutes, error_budget, is_retryable, retry_wait)


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


def scripted(outcomes, clock=None, cost=0.0):
    """A provider that replays a list of outcomes: an exception instance raises, anything else is returned."""
    items = list(outcomes)
    calls = []

    def fn(request, timeout_s):
        calls.append(request)
        if clock:
            clock.t += cost
        out = items.pop(0) if len(items) > 1 else items[0]
        if isinstance(out, Exception):
            raise out
        return out

    fn.calls = calls
    return fn


def test_retryable_kinds():
    assert is_retryable(ProviderFailure("timeout"))
    assert is_retryable(ProviderFailure("rate_limit", 429, 2.0))
    assert is_retryable(ProviderFailure("server_error", 500))
    assert not is_retryable(ProviderFailure("bad_request", 400))
    assert not is_retryable(ValueError("no kind"))


def test_backoff_without_jitter_doubles_then_caps():
    assert [backoff_delay(a, 0.5, 8.0, "none") for a in range(6)] == [0.5, 1.0, 2.0, 4.0, 8.0, 8.0]


def test_full_jitter_stays_inside_the_ceiling_and_spreads():
    rnd = random.Random(7)
    xs = [backoff_delay(3, 0.5, 8.0, "full", rnd) for _ in range(200)]
    assert all(0 <= x <= 4.0 for x in xs)
    assert max(xs) - min(xs) > 3.0
    assert backoff_delay(2, 1.0, 100.0, "full", type("R", (), {"random": lambda self: 0.5})()) == 2.0


def test_retry_wait_prefers_retry_after_but_respects_cap():
    rnd = random.Random(1)
    assert 2.0 <= retry_wait(ProviderFailure("rate_limit", 429, 2.0), 0, 0.5, 8.0, rnd) <= 2.5
    assert retry_wait(ProviderFailure("rate_limit", 429, 60.0), 0, 0.5, 8.0, rnd) >= 60.0
    w = retry_wait(ProviderFailure("server_error", 500), 2, 0.5, 8.0, rnd)
    assert 0 <= w <= 2.0


def test_breaker_opens_after_consecutive_failures_and_recovers_through_half_open():
    clk = Clock()
    b = CircuitBreaker(failure_threshold=3, cooldown_s=30, clock=clk)
    for _ in range(2):
        assert b.allow()
        b.record_failure()
    b.record_success()
    for _ in range(2):
        b.record_failure()
    assert b.state == "closed"
    b.record_failure()
    assert b.state == "open" and not b.allow()
    clk.t = 29.9
    assert b.state == "open"
    clk.t = 30.0
    assert b.state == "half_open"
    assert b.allow() and not b.allow()
    b.record_success()
    assert b.state == "closed" and b.allow()


def test_failed_probe_reopens_for_a_full_cooldown():
    clk = Clock()
    b = CircuitBreaker(failure_threshold=1, cooldown_s=10, clock=clk)
    b.record_failure()
    clk.t = 10
    assert b.allow()
    b.record_failure()
    assert b.state == "open"
    clk.t = 19.9
    assert not b.allow()
    clk.t = 20.0
    assert b.state == "half_open"
    assert [s for _, s in b.transitions] == ["open", "half_open", "open", "half_open"]


def test_retry_then_success_on_same_provider():
    clk = Clock()
    a = scripted([ProviderFailure("server_error", 500), ProviderFailure("timeout"), "ok-a"], clk)
    c = ResilientCaller([("a", a)], clock=clk, sleep=clk.sleep, rnd=random.Random(3))
    r = c.call("req")
    assert (r.value, r.provider, r.attempts, r.fallback_used) == ("ok-a", "a", 3, False)
    assert 0 < r.waited_s <= 0.5 + 1.0


def test_bad_request_is_not_retried_and_not_counted_against_the_provider():
    clk = Clock()
    a = scripted([ProviderFailure("bad_request", 400)], clk)
    b = scripted(["ok-b"], clk)
    c = ResilientCaller([("a", a), ("b", b)], clock=clk, sleep=clk.sleep)
    with pytest.raises(ProviderFailure):
        c.call("req")
    assert len(a.calls) == 1 and len(b.calls) == 0
    assert c.breakers["a"]._failures == 0


def test_fallback_when_primary_keeps_failing():
    clk = Clock()
    a = scripted([ProviderFailure("rate_limit", 429, 1.0)], clk)
    b = scripted(["ok-b"], clk)
    c = ResilientCaller([("a", a), ("b", b)], max_attempts=2, clock=clk, sleep=clk.sleep)
    r = c.call("req")
    assert (r.value, r.provider, r.fallback_used) == ("ok-b", "b", True)
    assert len(a.calls) == 2 and r.attempts == 3
    assert 1.0 <= clk.t <= 1.5


def test_retry_after_longer_than_cap_skips_retries_and_goes_to_fallback():
    clk = Clock()
    a = scripted([ProviderFailure("rate_limit", 429, 60.0)], clk)
    b = scripted(["ok-b"], clk)
    c = ResilientCaller([("a", a), ("b", b)], max_attempts=3, cap=8.0, clock=clk, sleep=clk.sleep)
    r = c.call("req")
    assert r.provider == "b" and len(a.calls) == 1 and clk.t == 0.0
    assert ("a", "retry_after_too_long") in r.log


def test_open_breaker_skips_the_provider_without_calling_it():
    clk = Clock()
    a = scripted([ProviderFailure("server_error", 500)], clk)
    b = scripted(["ok-b"], clk)
    br = {"a": CircuitBreaker(2, 30, clock=clk), "b": CircuitBreaker(2, 30, clock=clk)}
    c = ResilientCaller([("a", a), ("b", b)], br, max_attempts=3, clock=clk, sleep=clk.sleep)
    c.call("r1")
    assert br["a"].state == "open" and len(a.calls) == 2
    r = c.call("r2")
    assert r.provider == "b" and len(a.calls) == 2 and ("a", "circuit_open") in r.log


def test_deadline_stops_the_chain():
    clk = Clock()
    a = scripted([ProviderFailure("timeout")], clk, cost=6.0)
    b = scripted(["ok-b"], clk)
    c = ResilientCaller([("a", a), ("b", b)], max_attempts=3, deadline_s=10.0, clock=clk, sleep=clk.sleep)
    with pytest.raises(AllProvidersFailed) as e:
        c.call("req")
    assert e.value.reason == "deadline"
    assert len(b.calls) == 0


def test_everything_down_reports_every_attempt():
    clk = Clock()
    a = scripted([ProviderFailure("server_error", 500)], clk)
    b = scripted([ProviderFailure("timeout")], clk)
    c = ResilientCaller([("a", a), ("b", b)], max_attempts=2, clock=clk, sleep=clk.sleep)
    with pytest.raises(AllProvidersFailed) as e:
        c.call("req")
    assert e.value.attempts == [("a", "server_error"), ("a", "server_error"), ("b", "timeout"), ("b", "timeout")]


def test_error_budget_and_downtime():
    assert error_budget(0.995, 360000) == 1800
    assert error_budget(0.999, 360000) == 360
    assert downtime_minutes(0.999) == 43.2
    assert downtime_minutes(0.99, days=7) == 100.8
    s = budget_status(0.995, 360000, 2700)
    assert s["allowed"] == 1800 and s["remaining"] == -900 and s["burned"] == 1.5


def test_slis_exclude_client_errors_and_count_each_dimension():
    recs = ([{"status": "ok", "latency_ms": 900, "finish_reason": "stop"}] * 90
            + [{"status": "ok", "latency_ms": 5000, "finish_reason": "stop"}] * 5
            + [{"status": "ok", "latency_ms": 800, "finish_reason": "length"}] * 5
            + [{"status": "server_error", "latency_ms": 100}] * 10
            + [{"status": "bad_request", "latency_ms": 5}] * 50)
    s = compute_slis(recs, 3000)
    assert s["availability"] == pytest.approx(100 / 110)
    assert s["latency"] == pytest.approx(95 / 100)
    assert s["quality"] == pytest.approx(95 / 100)
    with pytest.raises(ValueError):
        compute_slis([{"status": "bad_request", "latency_ms": 1}], 3000)
