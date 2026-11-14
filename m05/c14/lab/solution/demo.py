import random

import online_monitor as om

ids = [f"r-{i:05d}" for i in range(2000)]
picked = [i for i in ids if om.should_sample(i, 0.02)]
print(f"sampled {len(picked)} of {len(ids)} requests, same again: {picked == [i for i in ids if om.should_sample(i, 0.02)]}")

rnd = random.Random(8)
samples = []
for _ in range(2000):
    good = rnd.random() < 0.85
    flagged = (not good and rnd.random() < 0.15) or (good and rnd.random() < 0.01)
    if flagged:
        samples.append((good, 1.0))
    elif om.should_sample(f"x{_}", 0.05):
        samples.append((good, 0.05))
print(f"{len(samples)} samples, naive pass rate {sum(g for g, _ in samples) / len(samples):.3f}, weighted {om.weighted_pass_rate(samples):.3f}")

lo, hi = om.wilson_interval(32, 40)
print(f"32 of 40 passed: interval [{lo:.2f}, {hi:.2f}]")
print(f"judge says 0.84 with TPR 0.92 and TNR 0.80: corrected {om.corrected_pass_rate(0.84, 0.92, 0.80):.3f}")
print(f"PSI of [50, 30, 20] against [20, 30, 50]: {om.psi([50, 30, 20], [20, 30, 50]):.3f}")
print(f"36 failures in 1000 requests with a 99.5% SLO: burn rate {om.burn_rate(36, 1000, 0.995):.1f}")
print("1h 9% and 5m 20%:", om.burn_alert({"1h": 0.09, "5m": 0.20}, 0.995))
print("1h 9% and 5m 0.1%:", om.burn_alert({"1h": 0.09, "5m": 0.001}, 0.995))
print("3d 0.6% and 6h 0.6%:", om.burn_alert({"3d": 0.006, "6h": 0.006}, 0.995))
