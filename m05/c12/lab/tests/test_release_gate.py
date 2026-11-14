import copy
import random

import pytest

import release_gate as rg


def scores(rnd, n, mean, sd=0.10):
    return [min(1.0, max(0.0, rnd.gauss(mean, sd))) for _ in range(n)]


def good_card():
    return {
        "identity": {"name": "Anh Ti AI Service", "version": "1"},
        "intended_use": ["chat support for branch staff"],
        "out_of_scope": ["hiring decisions"],
        "data_sources": [{"name": "messages.csv", "origin": "synthetic", "owner": "course", "license": "course material"}],
        "evaluation": [{"metric": "online score", "value": 0.82, "dataset": "scripted seed 7", "label": "Minh họa"}],
        "limitations": [
            "The small model can state a wrong policy with confidence.",
            "Redaction covers phones and addresses, not names.",
            "Only Vietnamese was evaluated in this release.",
        ],
        "oversight": {"owner": "platform team"},
        "config_digest": {"tenants.json": "0000"},
    }


def test_bucket_is_deterministic_and_in_range():
    assert rg.bucket("user-1", "s") == rg.bucket("user-1", "s")
    assert all(0 <= rg.bucket(f"u{i}", "s") < 100 for i in range(500))
    assert rg.bucket("user-1", "a") != rg.bucket("user-1", "b") or rg.bucket("user-2", "a") != rg.bucket("user-2", "b")


def test_route_share_close_to_percent():
    n = sum(rg.route(f"user-{i}", 10, "p2") == "canary" for i in range(4000))
    assert 0.08 * 4000 <= n <= 0.12 * 4000


def test_route_is_sticky_and_nested():
    users = [f"user-{i}" for i in range(1000)]
    assert [rg.route(u, 10, "p2") for u in users] == [rg.route(u, 10, "p2") for u in users]
    ten = {u for u in users if rg.route(u, 10, "p2") == "canary"}
    twenty_five = {u for u in users if rg.route(u, 25, "p2") == "canary"}
    assert ten <= twenty_five
    assert all(rg.route(u, 0, "p2") == "stable" for u in users)
    assert all(rg.route(u, 100, "p2") == "canary" for u in users)


def test_welch_t_sign_and_guard():
    rnd = random.Random(1)
    low, high = scores(rnd, 60, 0.6), scores(rnd, 60, 0.8)
    assert rg.welch_t(low, high) < -5
    assert rg.welch_t(high, low) > 5
    assert rg.welch_t([0.5], [0.5, 0.6]) == 0.0
    assert rg.welch_t([0.5, 0.5], [0.5, 0.5]) == 0.0


def test_controller_waits_without_enough_samples():
    rnd = random.Random(2)
    ctl = rg.CanaryController()
    assert ctl.observe(scores(rnd, 300, 0.82), scores(rnd, 12, 0.5)) == "wait"


def test_controller_rolls_back_after_two_bad_windows():
    rnd = random.Random(3)
    ctl = rg.CanaryController()
    assert ctl.observe(scores(rnd, 360, 0.82), scores(rnd, 40, 0.68, 0.12)) == "watch"
    assert ctl.observe(scores(rnd, 360, 0.82), scores(rnd, 40, 0.68, 0.12)) == "rollback"


def test_controller_resets_after_good_window():
    rnd = random.Random(4)
    ctl = rg.CanaryController()
    assert ctl.observe(scores(rnd, 360, 0.82), scores(rnd, 40, 0.65, 0.12)) == "watch"
    assert ctl.observe(scores(rnd, 360, 0.82), scores(rnd, 40, 0.83)) == "ok"
    assert ctl.observe(scores(rnd, 360, 0.82), scores(rnd, 40, 0.65, 0.12)) == "watch"


def test_small_noisy_drop_is_not_a_rollback():
    ctl = rg.CanaryController()
    stable = [0.82] * 300
    canary = [0.80, 0.84, 0.78] * 12
    assert ctl.observe(stable, canary) == "ok"


def test_run_rolls_back_bad_candidate():
    rnd = random.Random(5)
    run = rg.CanaryRun()
    for _ in range(8):
        run.step(scores(rnd, 360, 0.82), scores(rnd, 40, 0.68, 0.12))
    assert run.status == "rolled_back"
    assert run.history == ["watch", "rollback"]


def test_run_promotes_good_candidate_and_stops():
    rnd = random.Random(6)
    run = rg.CanaryRun(promote_after=4)
    for _ in range(4):
        run.step(scores(rnd, 360, 0.82), scores(rnd, 40, 0.83))
    assert run.status == "promoted"
    assert run.step(scores(rnd, 360, 0.82), scores(rnd, 40, 0.3)) == "promoted"
    assert len(run.history) == 4


def test_valid_card_has_no_issues():
    assert rg.validate_card(good_card()) == []


@pytest.mark.parametrize("mutate,needle", [
    (lambda c: c.pop("out_of_scope"), "out_of_scope"),
    (lambda c: c.update(limitations=["none", "n/a"]), "limitations"),
    (lambda c: c["evaluation"][0].pop("dataset"), "dataset"),
    (lambda c: c["evaluation"][0].update(label="measured"), "label"),
    (lambda c: c["data_sources"][0].pop("license"), "license"),
])
def test_card_problems_are_reported(mutate, needle):
    card = copy.deepcopy(good_card())
    mutate(card)
    issues = rg.validate_card(card)
    assert issues and any(needle in i for i in issues)


def test_stale_files(tmp_path):
    a, b = tmp_path / "tenants.json", tmp_path / "prices.json"
    a.write_text("{}")
    b.write_text('{"p": 1}')
    card = good_card()
    card["config_digest"] = {"tenants.json": rg.file_digest(a), "prices.json": rg.file_digest(b)}
    assert rg.stale_files(card, [a, b]) == []
    b.write_text('{"p": 2}')
    assert rg.stale_files(card, [a, b]) == ["prices.json"]
    card["config_digest"].pop("tenants.json")
    assert rg.stale_files(card, [a, b]) == ["prices.json", "tenants.json"]
