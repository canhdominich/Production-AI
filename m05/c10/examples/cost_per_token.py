from collections import defaultdict

from _kit import PriceTable, generate

prices = PriceTable()

print("one call: 400 prompt tokens, 120 output tokens")
for model in prices.models:
    p = prices.models[model]
    inp = 400 * p["input_per_mtok"] / 1e6
    outp = 120 * p["output_per_mtok"] / 1e6
    print(f"  {model:11} input ${inp:.6f}  output ${outp:.6f}  total ${inp + outp:.6f}  output share {outp / (inp + outp):.0%}")
cached = prices.cost("fake-medium", 400, 120, cached_tokens=300)
print(f"  fake-medium with 300 cached prompt tokens: ${cached:.6f} against ${prices.cost('fake-medium', 400, 120):.6f} without cache")

reqs = generate(5000, seed=42)
by = defaultdict(lambda: [0, 0, 0, 0.0, 0.0])
for r in reqs:
    c = prices.cost(r.model, r.prompt_tokens, r.output_tokens)
    row = by[r.feature]
    row[0] += 1
    row[1] += r.prompt_tokens
    row[2] += r.output_tokens
    row[3] += c
    row[4] += r.output_tokens * prices.models[r.model]["output_per_mtok"] / 1e6
total = sum(v[3] for v in by.values())
print(f"\n5000 requests of the base workload (seed 42), total ${total:.2f}")
print(f"{'feature':22}{'requests':>9}{'mean in':>9}{'mean out':>9}{'cost':>9}{'cost share':>11}")
for f, v in sorted(by.items(), key=lambda kv: -kv[1][3]):
    print(f"{f:22}{v[0] / 50:8.1f}%{v[1] / v[0]:9.0f}{v[2] / v[0]:9.0f} ${v[3]:8.2f}{v[3] / total:10.1%}")

out_cost = sum(v[4] for v in by.values())
in_rate = sum(prices.cost(r.model, r.prompt_tokens + r.output_tokens, 0) for r in reqs)
print(f"\noutput tokens are {out_cost / total:.0%} of the bill")
print(f"estimate that prices output like input: ${in_rate:.2f}, off by {(in_rate - total) / total:+.0%}")
