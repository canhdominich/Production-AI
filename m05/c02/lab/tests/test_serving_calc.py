import pytest

import serving_calc as sc

PROFILES = {
    "ollama": {"base_url": "http://localhost:11434/v1", "model": "qwen3:1.7b", "api_key": "ollama", "extra": {"reasoning_effort": "none"}},
    "vllm": {"base_url": "http://gpu-box:8000/v1/", "model": "Qwen/Qwen3-1.7B", "api_key": "token-abc123"},
}
MEDIUM = {"input_per_mtok": 0.75, "output_per_mtok": 3.00}


def test_resolve_uses_profile():
    cfg = sc.resolve_endpoint(PROFILES, "ollama", {})
    assert cfg == {"base_url": "http://localhost:11434/v1", "model": "qwen3:1.7b", "api_key": "ollama", "extra": {"reasoning_effort": "none"}}


def test_resolve_strips_trailing_slash_and_defaults_extra():
    cfg = sc.resolve_endpoint(PROFILES, "vllm", {})
    assert cfg["base_url"] == "http://gpu-box:8000/v1"
    assert cfg["extra"] == {}


def test_resolve_env_overrides():
    cfg = sc.resolve_endpoint(PROFILES, "ollama", {"CHAT_MODEL": "llama3.2", "CHAT_BASE_URL": "http://other:11434/v1/"})
    assert cfg["model"] == "llama3.2" and cfg["base_url"] == "http://other:11434/v1"


def test_resolve_rejects_missing_v1():
    with pytest.raises(ValueError):
        sc.resolve_endpoint(PROFILES, "ollama", {"CHAT_BASE_URL": "http://localhost:11434"})


def test_resolve_does_not_share_extra_dict():
    cfg = sc.resolve_endpoint(PROFILES, "ollama", {})
    cfg["extra"]["x"] = 1
    assert "x" not in PROFILES["ollama"]["extra"]


def test_api_cost_per_request():
    assert sc.api_cost_per_request(MEDIUM, 256, 242) == pytest.approx((256 * 0.75 + 242 * 3.0) / 1e6)


def test_selfhost_fixed_cost():
    assert sc.selfhost_fixed_cost(1.8, 1, 250) == pytest.approx(1.8 * 730 + 250)
    assert sc.selfhost_fixed_cost(2.0, 2, 0, hours=10) == pytest.approx(40.0)


def test_breakeven_requests():
    assert sc.breakeven_requests(1564.0, 0.001) == pytest.approx(1_564_000)
    with pytest.raises(ValueError):
        sc.breakeven_requests(1564.0, 0)


def test_required_utilization():
    capacity = 1200 * 730 * 3600
    assert sc.required_utilization(1_000_000, 242, 1200, 1) == pytest.approx(1_000_000 * 242 / capacity)
    assert sc.required_utilization(1_000_000, 242, 1200, 2) == pytest.approx(1_000_000 * 242 / (2 * capacity))


def test_decide_three_outcomes():
    assert sc.decide(100_000, 0.0009, 1564, 0.01) == "api"
    assert sc.decide(5_000_000, 0.0009, 1564, 0.38) == "self-host"
    assert sc.decide(5_000_000, 0.0009, 1564, 0.9) == "self-host-needs-more-gpus"
    assert sc.decide(5_000_000, 0.0009, 1564, 0.6) == "self-host"
