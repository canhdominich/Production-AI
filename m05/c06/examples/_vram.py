import json
from pathlib import Path

CFG = json.loads((Path(__file__).resolve().parent / "models.json").read_text(encoding="utf-8"))
GIB = 1024 ** 3
MIB = 1024 ** 2


def param_count(m, stored_output_copy=False):
    h, hd = m["hidden_size"], m["head_dim"]
    attn = h * m["heads"] * hd + 2 * h * m["kv_heads"] * hd + m["heads"] * hd * h + 2 * hd
    mlp = 3 * h * m["intermediate"]
    per_layer = attn + mlp + 2 * h
    embed = m["vocab"] * h
    copies = 1 if m["tie_embeddings"] and not stored_output_copy else 2
    return embed * copies + m["layers"] * per_layer + h


def weight_bytes(params, bits_per_weight):
    return params * bits_per_weight / 8


def kv_bytes_per_token(m, kv_dtype_bytes=2):
    return 2 * m["layers"] * m["kv_heads"] * m["head_dim"] * kv_dtype_bytes


def kv_cache_bytes(m, ctx, seqs, kv_dtype_bytes=2):
    return kv_bytes_per_token(m, kv_dtype_bytes) * ctx * seqs


def activation_bytes(m, batched_tokens, act_dtype_bytes=2):
    return batched_tokens * (4 * m["hidden_size"] + 2 * m["intermediate"]) * act_dtype_bytes


def vram_budget(m, bits, ctx, seqs, batched_tokens=4096, overhead_gib=1.0, util=0.9):
    w = weight_bytes(param_count(m), bits)
    kv = kv_cache_bytes(m, ctx, seqs)
    act = activation_bytes(m, batched_tokens)
    used = w + kv + act + overhead_gib * GIB
    return {"weights": w, "kv": kv, "activation": act, "overhead": overhead_gib * GIB, "used": used, "card_needed": used / util}


def max_sequences(m, bits, ctx, card_gib, batched_tokens=4096, overhead_gib=1.0, util=0.9):
    fixed = weight_bytes(param_count(m), bits) + activation_bytes(m, batched_tokens) + overhead_gib * GIB
    free = card_gib * GIB * util - fixed
    return max(0, int(free // kv_cache_bytes(m, ctx, 1)))
