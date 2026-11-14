import math

import pytest

import online_monitor as om


def test_sampling_is_deterministic():
    ids = [f"r-{i:05d}" for i in range(2000)]
    first = [om.should_sample(i, 0.05) for i in ids]
    assert first == [om.should_sample(i, 0.05) for i in ids]


def test_sampling_rate_is_close_to_target():
    ids = [f"r-{i:05d}" for i in range(20000)]
    share = sum(om.should_sample(i, 0.05) for i in ids) / len(ids)
    assert 0.04 < share < 0.06


def test_sampling_edges_and_salt():
    assert not om.should_sample("r-1", 0.0)
    assert om.should_sample("r-1", 1.0)
    ids = [f"r-{i:05d}" for i in range(2000)]
    a = {i for i in ids if om.should_sample(i, 0.1, salt="a")}
    b = {i for i in ids if om.should_sample(i, 0.1, salt="b")}
    assert a != b


def test_weighted_pass_rate_corrects_oversampled_failures():
    samples = [(False, 1.0)] * 10 + [(True, 0.1)] * 5 + [(False, 0.1)] * 1
    assert om.weighted_pass_rate(samples) == pytest.approx(50 / 70)
    naive = sum(p for p, _ in samples) / len(samples)
    assert naive < om.weighted_pass_rate(samples)


def test_weighted_pass_rate_equal_weights_is_plain_mean():
    assert om.weighted_pass_rate([(True, 0.5), (False, 0.5), (True, 0.5), (True, 0.5)]) == pytest.approx(0.75)


def test_weighted_pass_rate_rejects_empty():
    with pytest.raises(ValueError):
        om.weighted_pass_rate([])


def test_wilson_known_values():
    lo, hi = om.wilson_interval(16, 20)
    assert lo == pytest.approx(0.584, abs=0.005)
    assert hi == pytest.approx(0.919, abs=0.005)


def test_wilson_edges():
    assert om.wilson_interval(0, 0) == (0.0, 1.0)
    lo, hi = om.wilson_interval(20, 20)
    assert hi == pytest.approx(1.0) and 0.8 < lo < 0.9
    lo, hi = om.wilson_interval(0, 20)
    assert lo == pytest.approx(0.0) and 0.1 < hi < 0.2


def test_wilson_narrows_with_more_samples():
    small = om.wilson_interval(8, 10)
    large = om.wilson_interval(800, 1000)
    assert (large[1] - large[0]) < (small[1] - small[0])


def test_corrected_pass_rate():
    assert om.corrected_pass_rate(0.84, 0.92, 0.80) == pytest.approx((0.84 + 0.8 - 1) / 0.72)
    assert om.corrected_pass_rate(0.5, 1.0, 1.0) == pytest.approx(0.5)


def test_corrected_pass_rate_is_clamped_and_guarded():
    assert om.corrected_pass_rate(0.99, 0.9, 0.8) == 1.0
    assert om.corrected_pass_rate(0.01, 0.9, 0.8) == 0.0
    with pytest.raises(ValueError):
        om.corrected_pass_rate(0.5, 0.5, 0.5)


def test_psi_zero_and_symmetric():
    assert om.psi([10, 20, 30], [1, 2, 3]) == pytest.approx(0.0, abs=1e-9)
    a, b = [50, 30, 20], [20, 30, 50]
    assert om.psi(a, b) == pytest.approx(om.psi(b, a))
    assert om.psi(a, b) > 0.25


def test_psi_value_and_empty_bucket():
    expected = [0.5 * 100, 0.5 * 100]
    actual = [0.8 * 100, 0.2 * 100]
    want = (0.8 - 0.5) * math.log(0.8 / 0.5) + (0.2 - 0.5) * math.log(0.2 / 0.5)
    assert om.psi(expected, actual) == pytest.approx(want)
    assert math.isfinite(om.psi([10, 10], [20, 0]))


def test_burn_rate():
    assert om.burn_rate(36, 1000, 0.995) == pytest.approx(7.2)
    assert om.burn_rate(5, 1000, 0.995) == pytest.approx(1.0)
    assert om.burn_rate(0, 0, 0.995) == 0.0


def test_burn_alert_requires_both_windows():
    slo = 0.995
    assert om.burn_alert({"1h": 0.10, "5m": 0.20, "6h": 0.01, "30m": 0.01}, slo) == "page"
    assert om.burn_alert({"1h": 0.10, "5m": 0.001, "6h": 0.02, "30m": 0.001}, slo) is None
    assert om.burn_alert({"6h": 0.05, "30m": 0.05}, slo) == "page"


def test_burn_alert_ticket_and_priority():
    slo = 0.995
    assert om.burn_alert({"1d": 0.02, "2h": 0.02}, slo) == "ticket"
    assert om.burn_alert({"3d": 0.006, "6h": 0.006}, slo) == "ticket"
    assert om.burn_alert({"3d": 0.006, "6h": 0.006, "1h": 0.1, "5m": 0.1}, slo) == "page"
    assert om.burn_alert({}, slo) is None


def test_burn_alert_threshold_is_strict():
    assert om.burn_alert({"1h": 14.4 * 0.005, "5m": 14.4 * 0.005}, 0.995) is None


def panel(i, x, y, w=12, expr="llm:error_ratio_rate5m"):
    return {"id": i, "gridPos": {"h": 8, "w": w, "x": x, "y": y}, "targets": [{"refId": "A", "expr": expr}]}


KNOWN = {"llm_requests_total", "llm:error_ratio_rate5m", "llm_request_duration_seconds_bucket"}


def test_dashboard_clean():
    dash = {"panels": [panel(1, 0, 0), panel(2, 12, 0), panel(3, 0, 8)]}
    assert om.dashboard_problems(dash, KNOWN) == []


def test_dashboard_detects_each_problem():
    dup = om.dashboard_problems({"panels": [panel(1, 0, 0), panel(1, 12, 0)]}, KNOWN)
    assert any("duplicate" in e and "1" in e for e in dup)
    over = om.dashboard_problems({"panels": [panel(1, 0, 0), panel(2, 6, 4)]}, KNOWN)
    assert any("overlap" in e for e in over)
    wide = om.dashboard_problems({"panels": [panel(1, 18, 0, w=12)]}, KNOWN)
    assert any("24" in e for e in wide)
    missing = om.dashboard_problems({"panels": [{"id": 1, "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0}}]}, KNOWN)
    assert any("no query" in e for e in missing)
    typo = om.dashboard_problems({"panels": [panel(7, 0, 0, expr="rate(llm_request_seconds_bucket[5m])")]}, KNOWN)
    assert typo == ["panel 7 uses unknown metric llm_request_seconds_bucket"]
