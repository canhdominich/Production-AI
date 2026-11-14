import math

import numpy as np

from _kit import wilson

print("half width of the 95% interval when the pass rate is 0.80")
for n in (20, 40, 100, 400, 1600):
    lo, hi = wilson(round(0.8 * n), n)
    print(f"n={n:5}  interval=[{lo:.2f}, {hi:.2f}]  half width {(hi - lo) / 2:.3f}")

BASE, DROP, Z = 0.82, 0.66, 2.33
rng = np.random.default_rng(14)


def fires(passes, n):
    se = math.sqrt(BASE * (1 - BASE) / n)
    return (passes / n - BASE) / se < -Z


print(f"\nalarm when the sampled pass rate is {Z} standard errors below {BASE} (one sided, about 1%)")
print(f"{'samples per day':>16}{'false alarms':>14}{'catch the drop to 0.66':>24}")
for n in (10, 20, 40, 100):
    trials = 4000
    quiet = rng.binomial(n, BASE, trials)
    drop = rng.binomial(n, DROP, trials)
    fa = np.mean([fires(x, n) for x in quiet])
    hit = np.mean([fires(x, n) for x in drop])
    print(f"{n:>16}{fa:>14.1%}{hit:>24.1%}")

print("\npooling 3 days of 20 samples (n=60) instead of 1 day of 20:")
quiet = rng.binomial(60, BASE, 4000)
drop = rng.binomial(60, DROP, 4000)
print(f"false alarms {np.mean([fires(x, 60) for x in quiet]):.1%}, catch {np.mean([fires(x, 60) for x in drop]):.1%}, but the alarm is up to 3 days late")
