from _vram import CFG, GIB, kv_bytes_per_token, max_sequences, vram_budget

A = CFG["assumptions"]
SEQS = A["concurrent_sequences"]
print(f"{SEQS} concurrent sequences, bf16 KV cache; sizes in GiB")
print("model       quant ctx     weights    kv   act  total  card   24GB 80GB")
for name, m in CFG["models"].items():
    for q in ("bf16", "int4"):
        for ctx in (4096, 32768):
            b = vram_budget(m, CFG["quant_bits_per_weight"][q], ctx, SEQS, A["batched_tokens"], A["runtime_overhead_gib"], A["memory_utilization"])
            card = b["card_needed"] / GIB
            fit = lambda g: "yes" if card <= g else "NO"
            print(f"{name:<11} {q:<5} {ctx:>5} {b['weights'] / GIB:>10.1f} {b['kv'] / GIB:>5.1f} {b['activation'] / GIB:>5.2f} {b['used'] / GIB:>6.1f} {card:>5.1f} {fit(24):>5} {fit(80):>4}")
print()
for name, m in CFG["models"].items():
    print(f"{name}: KV cache {kv_bytes_per_token(m) // 1024} KiB per token")

m8 = CFG["models"]["qwen3-8b"]
print("\nqwen3-8b on one 24 GiB card: sequences that still fit")
for q in ("bf16", "int4"):
    row = [f"ctx {ctx}: {max_sequences(m8, CFG['quant_bits_per_weight'][q], ctx, 24)}" for ctx in (4096, 8192, 32768)]
    print(f"{q:<5}", " | ".join(row))
