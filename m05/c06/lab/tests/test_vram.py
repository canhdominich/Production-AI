import pytest

from vram import GIB, activation_bytes, fits, kv_bytes_per_token, kv_cache_bytes, max_sequences, param_count, relative_error, vram_budget, weight_bytes

SMALL = {"hidden_size": 2048, "layers": 28, "heads": 16, "kv_heads": 8, "head_dim": 128, "intermediate": 6144, "vocab": 151936, "tie_embeddings": True}
MEDIUM = {"hidden_size": 4096, "layers": 36, "heads": 32, "kv_heads": 8, "head_dim": 128, "intermediate": 12288, "vocab": 151936, "tie_embeddings": False}


def test_param_count_untied_matches_published():
    assert param_count(MEDIUM) == 8190735360


def test_param_count_tied_counts_embedding_once():
    assert param_count(SMALL) == 1720574976
    assert param_count(SMALL, stored_output_copy=True) == 2031739904


def test_kv_bytes_per_token():
    assert kv_bytes_per_token(SMALL) == 114688
    assert kv_bytes_per_token(MEDIUM) == 147456
    assert kv_bytes_per_token(SMALL, kv_dtype_bytes=1) == 57344


def test_kv_cache_scales_with_context_and_sequences():
    assert kv_cache_bytes(SMALL, 4096, 8) == 3.5 * GIB
    assert kv_cache_bytes(SMALL, 8192, 8) == 2 * kv_cache_bytes(SMALL, 4096, 8)
    assert kv_cache_bytes(SMALL, 4096, 16) == 2 * kv_cache_bytes(SMALL, 4096, 8)


def test_kv_cache_rejects_non_positive_inputs():
    with pytest.raises(ValueError):
        kv_cache_bytes(SMALL, 0, 8)
    with pytest.raises(ValueError):
        kv_cache_bytes(SMALL, 4096, 0)


def test_weight_bytes():
    assert weight_bytes(1_000_000_000, 16) == 2_000_000_000
    assert weight_bytes(1_000_000_000, 4.5) == 562_500_000
    with pytest.raises(ValueError):
        weight_bytes(1_000_000_000, 0)


def test_activation_bytes():
    assert activation_bytes(SMALL, 4096) == 4096 * (4 * 2048 + 2 * 6144) * 2
    assert activation_bytes(SMALL, 512, act_dtype_bytes=4) == 512 * 20480 * 4


def test_budget_adds_up():
    b = vram_budget(MEDIUM, 16, 4096, 8)
    assert b["used"] == pytest.approx(b["weights"] + b["kv"] + b["activation"] + b["overhead"])
    assert b["card_needed"] == pytest.approx(b["used"] / 0.9)
    assert b["overhead"] == GIB


def test_budget_checks_util():
    with pytest.raises(ValueError):
        vram_budget(MEDIUM, 16, 4096, 8, util=0)
    with pytest.raises(ValueError):
        vram_budget(MEDIUM, 16, 4096, 8, util=1.2)


def test_fits_boundary():
    b = vram_budget(MEDIUM, 16, 4096, 8)
    assert fits(b, 24)
    assert not fits(b, 22)
    assert not fits(vram_budget(MEDIUM, 16, 32768, 8), 24)


def test_max_sequences():
    assert max_sequences(MEDIUM, 16, 4096, 24) == 8
    assert max_sequences(MEDIUM, 16, 4096, 12) == 0
    assert max_sequences(MEDIUM, 4.5, 4096, 24) > max_sequences(MEDIUM, 16, 4096, 24)


def test_relative_error_sign():
    assert relative_error(90, 100) == pytest.approx(-0.1)
    assert relative_error(110, 100) == pytest.approx(0.1)


def test_config_not_modified():
    before = dict(SMALL)
    vram_budget(SMALL, 16, 4096, 8)
    assert SMALL == before
