import random


def gate_blocks(base_rate, cand_rate, n, rule, rng, margin):
    base = sum(rng.random() < base_rate for _ in range(n)) / n
    cand = sum(rng.random() < cand_rate for _ in range(n)) / n
    if rule == "strict":
        return cand < base
    return cand < base - margin


def simulate(n, rule, true_cand, margin=0.05, runs=2000, seed=7):
    rng = random.Random(seed)
    return sum(gate_blocks(0.85, true_cand, n, rule, rng, margin) for _ in range(runs)) / runs


print("model quality 0.85 on the baseline; 2000 simulated pull requests per cell")
print(f"{'cases':>6} {'rule':>10} {'unchanged model':>16} {'real drop to 0.70':>18}")
for n in (24, 100, 400):
    for rule in ("strict", "tolerance"):
        same = simulate(n, rule, 0.85)
        worse = simulate(n, rule, 0.70)
        print(f"{n:>6} {rule:>10} {same:>15.1%} {worse:>17.1%}")
