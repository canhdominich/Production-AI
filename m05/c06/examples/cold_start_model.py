from _vram import CFG, GIB, param_count, weight_bytes

IMAGE_GIB, IMAGE_GIB_PER_S = 8.0, 1.0
WARMUP_S = 30.0
STORAGE_GIB_PER_S = {"network volume": 0.5, "local NVMe": 2.0}


def cold_start_s(weights_gib, storage_gib_per_s, new_node_boot_s=0.0):
    return new_node_boot_s + IMAGE_GIB / IMAGE_GIB_PER_S + weights_gib / storage_gib_per_s + WARMUP_S


print(f"image {IMAGE_GIB:.0f} GiB at {IMAGE_GIB_PER_S} GiB/s, warmup {WARMUP_S:.0f} s, node already running")
print("model       quant  weights_GiB  network_volume_s  local_NVMe_s")
for name, m in CFG["models"].items():
    for q in ("bf16", "int4"):
        w = weight_bytes(param_count(m), CFG["quant_bits_per_weight"][q]) / GIB
        a, b = (cold_start_s(w, v) for v in STORAGE_GIB_PER_S.values())
        print(f"{name:<11} {q:<5} {w:>11.1f} {a:>17.0f} {b:>13.0f}")
extra = cold_start_s(15.3, 0.5, new_node_boot_s=90)
print(f"qwen3-8b bf16 on a brand new node (90 s boot assumed): {extra:.0f} s")
