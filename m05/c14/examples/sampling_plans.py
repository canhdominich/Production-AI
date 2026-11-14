from collections import Counter

from _kit import FEATURES, day_log, unit_hash, wilson

UNIFORM = {f: 0.02 for f in FEATURES}
STRATIFIED = {"chat": 0.010, "knowledge_assistant": 0.030, "weekly_report_agent": 0.17}

log = day_log(0)


def pick(rows, rates, salt="eval-v1"):
    return [r for r in rows if unit_hash(r["id"], salt) < rates[r["feature"]]]


total, uni, strat = Counter(r["feature"] for r in log), pick(log, UNIFORM), pick(log, STRATIFIED)
cu, cs = Counter(r["feature"] for r in uni), Counter(r["feature"] for r in strat)
print(f"{'feature':22}{'requests':>9}{'uniform 2%':>12}{'stratified':>12}")
for f in FEATURES:
    print(f"{f:22}{total[f]:>9}{cu[f]:>12}{cs[f]:>12}")
print(f"{'all':22}{len(log):>9}{len(uni):>12}{len(strat):>12}")

again = {r["id"] for r in pick(log, STRATIFIED)}
print("same ids on a second replica:", again == {r["id"] for r in strat})
other = {r["id"] for r in pick(log, STRATIFIED, salt="eval-v2")}
print("overlap with a new salt:", len(other & again), "of", len(again))

print("\nstratified estimate per feature (true value from all 2000 requests):")
for f in FEATURES:
    mine = [r for r in strat if r["feature"] == f]
    allf = [r for r in log if r["feature"] == f]
    lo, hi = wilson(sum(r["good"] for r in mine), len(mine))
    print(f"{f:22} n={len(mine):3} pass={sum(r['good'] for r in mine) / len(mine):.2f} interval=[{lo:.2f}, {hi:.2f}] true={sum(r['good'] for r in allf) / len(allf):.2f}")
w = {f: 1 / STRATIFIED[f] for f in FEATURES}
est = sum(w[r["feature"]] * r["good"] for r in strat) / sum(w[r["feature"]] for r in strat)
naive = sum(r["good"] for r in strat) / len(strat)
true = sum(r["good"] for r in log) / len(log)
print(f"\nall features: naive mean {naive:.3f}, weighted by 1/rate {est:.3f}, true {true:.3f}")

naive_days, weighted_days, true_days = [], [], []
for day in range(14):
    rows = day_log(day)
    s = pick(rows, STRATIFIED)
    naive_days.append(sum(r["good"] for r in s) / len(s))
    weighted_days.append(sum(w[r["feature"]] * r["good"] for r in s) / sum(w[r["feature"]] for r in s))
    true_days.append(sum(r["good"] for r in rows) / len(rows))
mean = lambda xs: sum(xs) / len(xs)
print(f"mean of 14 days: naive {mean(naive_days):.3f}, weighted {mean(weighted_days):.3f}, true {mean(true_days):.3f}")
