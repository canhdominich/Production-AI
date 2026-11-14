import math

from _vram import CFG, GIB, vram_budget

A = CFG["assumptions"]
H100_GIB = 80
PODS = [("1.7b int4", "qwen3-1.7b", "int4"), ("1.7b bf16", "qwen3-1.7b", "bf16"), ("8b int4 a", "qwen3-8b", "int4"),
        ("8b int4 b", "qwen3-8b", "int4"), ("8b bf16", "qwen3-8b", "bf16"), ("32b int4", "qwen3-32b", "int4")]
need = {}
for label, name, q in PODS:
    b = vram_budget(CFG["models"][name], CFG["quant_bits_per_weight"][q], 4096, 4, A["batched_tokens"], A["runtime_overhead_gib"], A["memory_utilization"])
    need[label] = b["card_needed"] / GIB
print("pod        VRAM needed (GiB), 4 sequences, context 4096")
for label, v in need.items():
    print(f"{label:<10} {v:>6.1f}")

nodes = 4
print(f"\nCluster: {nodes} nodes, one 80 GiB GPU each. Pods: {len(PODS)}, total need {sum(need.values()):.0f} GiB")

placed = list(need)[:nodes]
pending = list(need)[nodes:]
used = sum(need[p] for p in placed)
print(f"\n1) whole GPU per pod: placed {len(placed)}, Pending {len(pending)} ({', '.join(pending)}); VRAM used {used:.0f} of {nodes * H100_GIB} GiB = {100 * used / (nodes * H100_GIB):.0f}%")

layouts = [("7 x 1g.10gb", [10] * 7), ("3 x 2g.20gb", [20] * 3), ("2 x 3g.40gb", [40] * 2), ("1 x 7g.80gb", [80])]
free = [(g, size) for g, sizes in layouts for size in sizes]
slices, left = [], list(free)
for label in need:
    fit = sorted((s for s in left if s[1] >= need[label]), key=lambda s: s[1])
    if fit:
        left.remove(fit[0])
        slices.append((label, fit[0][1]))
reserved = sum(s for _, s in slices)
print(f"2) MIG layouts per node: placed {len(slices)} of {len(PODS)}; slices reserved {reserved} GiB for {sum(need[l] for l, _ in slices):.0f} GiB of need; {len(left)} slices still free")
print("   slices: " + ", ".join(f"{l} in {s} GiB" for l, s in slices))

REPLICAS = 4


def time_slicing(claims):
    used, failed = {}, []
    for i, label in enumerate(need):
        gpu = i // REPLICAS
        if used.get(gpu, 0) + claims[label] <= H100_GIB:
            used[gpu] = used.get(gpu, 0) + claims[label]
        else:
            failed.append(label)
    return used, failed


default_claims = {label: 0.9 * H100_GIB for label in need}
used, failed = time_slicing(default_claims)
print(f"3) time-slicing, {REPLICAS} replicas per GPU; the scheduler accepts all {len(PODS)} pods because it counts replicas, not memory")
print(f"   vLLM default gpu-memory-utilization 0.9: each pod claims {0.9 * H100_GIB:.0f} GiB, failed at start {len(failed)} of {len(PODS)}: {', '.join(failed)}")
tuned = {label: math.ceil(need[label] / H100_GIB / 0.05) * 0.05 * H100_GIB for label in need}
used, failed = time_slicing(tuned)
print(f"   explicit fractions rounded up from the need: claims {', '.join(f'{v:.0f}' for v in tuned.values())} GiB, failed {len(failed)}")
print(f"   GPU 0 claims {used[0]:.0f} GiB and GPU 1 claims {used[1]:.0f} GiB of 80; no memory isolation between replicas")
