from _vram import CFG, param_count

print("model         computed        published    gap")
for name, m in CFG["models"].items():
    got = param_count(m)
    pub = m["published_params"]
    print(f"{name:<12} {got:>14,} {pub:>14,} {100 * (got - pub) / pub:>+6.1f}%")

m = CFG["models"]["qwen3-1.7b"]
with_copy = param_count(m, stored_output_copy=True)
print(f"qwen3-1.7b with a stored output copy: {with_copy:,} ({100 * (with_copy - m['published_params']) / m['published_params']:+.1f}%)")
