import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "platform"))
from common import percentile
from workload import generate

reqs = generate(3000, seed=42)
by = defaultdict(list)
for r in reqs:
    by[r.feature].append(r)

print(f"{'feature':22}{'n':>6}  {'prompt p50/p95/max':>20}  {'output p50/p95/max':>20}")
for f, rs in by.items():
    p = [r.prompt_tokens for r in rs]
    o = [r.output_tokens for r in rs]
    print(f"{f:22}{len(rs):>6}  {percentile(p, 50):>6.0f}/{percentile(p, 95):>5.0f}/{max(p):>6}  {percentile(o, 50):>6.0f}/{percentile(o, 95):>5.0f}/{max(o):>6}")

out_total = sum(r.output_tokens for r in reqs)
print()
for f, rs in by.items():
    print(f"{f:22} {len(rs) / len(reqs):6.1%} of requests, {sum(r.output_tokens for r in rs) / out_total:6.1%} of output tokens")

median_out = percentile([r.output_tokens for r in reqs], 50)
mean_out = out_total / len(reqs)
print()
print(f"median output {median_out:.0f} tokens, mean output {mean_out:.0f} tokens")
print(f"a test with every request at the median generates {median_out / mean_out:.0%} of the real output load")
