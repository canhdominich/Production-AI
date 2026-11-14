import numpy as np
from scipy.stats import ks_2samp

from _kit import generate, psi


def tokens(seed, n=1200):
    return np.array([r.prompt_tokens for r in generate(n, seed=seed) if r.feature == "knowledge_assistant"], dtype=float)


reference = np.concatenate([tokens(s) for s in (201, 202, 203)])
same = tokens(204)
longer = tokens(205) * 1.35
edges = np.quantile(reference, np.linspace(0, 1, 11)[1:-1])


def decile_counts(x):
    return np.bincount(np.searchsorted(edges, x), minlength=10)


print(f"reference: {len(reference)} knowledge-assistant prompts, p50 {np.percentile(reference, 50):.0f}, p95 {np.percentile(reference, 95):.0f} tokens")
for name, x in (("new week, same behaviour", same), ("new week, retrieval returns 35% more text", longer)):
    ks = ks_2samp(reference, x)
    print(f"{name:42} n={len(x):3} p50 {np.percentile(x, 50):4.0f} p95 {np.percentile(x, 95):4.0f}  KS {ks.statistic:.3f} p={ks.pvalue:.2g}  PSI(deciles) {psi(decile_counts(reference), decile_counts(x)):.3f}")
cost_ratio = longer.mean() / reference.mean()
print(f"mean prompt grows by a factor of {cost_ratio:.2f}, so input-token cost for this feature grows by the same factor")
