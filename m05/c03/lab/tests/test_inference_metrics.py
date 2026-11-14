import pytest

from inference_metrics import goodput, max_concurrency_within_slo, meets_slo, throughput, tpot, ttft, window

FAST = {"sent": 0.0, "token_times": [0.5, 0.6, 0.7, 0.8, 0.9]}
QUEUED = {"sent": 0.0, "token_times": [4.0, 4.1, 4.2, 4.3, 4.4]}
SLOW = {"sent": 0.0, "token_times": [0.5, 1.5, 2.5, 3.5, 4.5]}


def test_ttft_and_tpot():
    assert ttft(FAST) == pytest.approx(0.5)
    assert tpot(FAST) == pytest.approx(0.1)
    assert tpot({"sent": 0.0, "token_times": [1.0]}) == 0.0


def test_window_and_throughput():
    recs = [FAST, QUEUED]
    assert window(recs) == pytest.approx(4.4)
    assert throughput(recs) == pytest.approx(10 / 4.4)


def test_meets_slo_needs_both_conditions():
    assert meets_slo(FAST, 1.0, 0.2)
    assert not meets_slo(QUEUED, 1.0, 0.2)
    assert not meets_slo(SLOW, 1.0, 0.2)


def test_goodput_counts_only_good_tokens():
    recs = [FAST, QUEUED, SLOW]
    assert goodput(recs, 1.0, 0.2) == pytest.approx(5 / 4.5)
    assert goodput(recs, 1.0, 0.2) < throughput(recs)


def test_max_concurrency_stops_at_first_failure():
    curve = [{"concurrency": 8, "ok_fraction": 0.95}, {"concurrency": 1, "ok_fraction": 1.0},
             {"concurrency": 32, "ok_fraction": 0.2}, {"concurrency": 16, "ok_fraction": 0.5},
             {"concurrency": 64, "ok_fraction": 0.95}]
    assert max_concurrency_within_slo(curve) == 8
    assert max_concurrency_within_slo(curve, 0.4) == 16
    assert max_concurrency_within_slo([]) == 0
