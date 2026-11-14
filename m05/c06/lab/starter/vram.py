GIB = 1024 ** 3


def param_count(m, stored_output_copy=False):
    # TODO 1: cộng embedding (một hoặc hai bản), các lớp attention và MLP, norm cuối
    raise NotImplementedError


def weight_bytes(params, bits_per_weight):
    # TODO 2: byte = tham số x bit / 8; báo ValueError nếu bits <= 0
    raise NotImplementedError


def kv_bytes_per_token(m, kv_dtype_bytes=2):
    # TODO 3: 2 (K và V) x lớp x kv_heads x head_dim x byte
    raise NotImplementedError


def kv_cache_bytes(m, ctx, seqs, kv_dtype_bytes=2):
    # TODO 4: byte mỗi token x ctx x seqs; báo ValueError nếu ctx hoặc seqs <= 0
    raise NotImplementedError


def activation_bytes(m, batched_tokens, act_dtype_bytes=2):
    # TODO 5: batched_tokens x (4 x hidden + 2 x intermediate) x byte
    raise NotImplementedError


def vram_budget(m, bits, ctx, seqs, batched_tokens=4096, overhead_gib=1.0, util=0.9):
    # TODO 6: trả dict weights, kv, activation, overhead, used, card_needed (= used / util); util phải trong (0, 1]
    raise NotImplementedError


def fits(budget, card_gib):
    # TODO 7: True nếu card_needed không vượt dung lượng thẻ (GiB)
    raise NotImplementedError


def max_sequences(m, bits, ctx, card_gib, batched_tokens=4096, overhead_gib=1.0, util=0.9):
    # TODO 8: số chuỗi đồng thời tối đa còn chứa được KV cache sau khi trừ trọng số, activation, overhead
    raise NotImplementedError


def relative_error(estimate, measured):
    # TODO 9: (ước lượng - số đo) / số đo
    raise NotImplementedError
