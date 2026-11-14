import csv
from collections import Counter

import numpy as np
from scipy.stats import chi2_contingency

from _kit import MESSAGES, psi

with open(MESSAGES, encoding="utf-8", newline="") as f:
    intents = [row["intent"] for row in csv.DictReader(f)]
LABELS = sorted(set(intents))
BASE = np.array([Counter(intents)[k] for k in LABELS], dtype=float)
BASE /= BASE.sum()
rng = np.random.default_rng(14)


def week(weights, n):
    return rng.multinomial(n, weights / weights.sum())


def tilt(**factors):
    w = BASE.copy()
    for k, v in factors.items():
        w[LABELS.index(k)] *= v
    return w


print("intent mix of the 300 customer messages (baseline):")
print("  " + ", ".join(f"{k} {p:.0%}" for k, p in zip(LABELS, BASE)))
reference = week(BASE, 1500)
same = week(BASE, 1500)
peak = week(tilt(complaint_late=3.0, refund=2.0, eta=1.5), 1500)
for name, counts in (("same mix, new week", same), ("peak-season mix", peak)):
    p = chi2_contingency(np.array([reference, counts]))[1]
    print(f"{name:20} PSI {psi(reference, counts):.3f}   chi-square p-value {p:.3g}")
print("  after the shift: " + ", ".join(f"{k} {c / peak.sum():.0%}" for k, c in zip(LABELS, peak)))

print("\nnoise of PSI when nothing changed (500 repeats, same mix both sides):")
for n in (50, 200, 1500):
    scores = [psi(week(BASE, n), week(BASE, n)) for _ in range(500)]
    print(f"n={n:5} median {np.median(scores):.3f}  95th percentile {np.percentile(scores, 95):.3f}")

weekday, saturday = tilt(order_status=1.1), tilt(order_status=0.7, eta=1.6, other=1.3)
mon_fri = week(weekday, 7500)
print("\nseasonality inside the week (saturday has its own mix):")
print(f"saturday vs the Monday to Friday week: PSI {psi(mon_fri, week(saturday, 1500)):.3f}")
last_saturdays = sum(week(saturday, 1500) for _ in range(4))
print(f"saturday vs the last 4 saturdays:      PSI {psi(last_saturdays, week(saturday, 1500)):.3f}")
