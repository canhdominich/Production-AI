import random

import _kit  # noqa: F401
from anhti_platform.canary import CanaryRouter, RollbackController

STABLE_Q, GOOD_Q, BAD_Q = 0.90, 0.92, 0.62


def trial(canary_q, min_samples, seed, per_window=None):
    rnd = random.Random(seed)
    router = CanaryRouter(percent=10)
    ctl = RollbackController(router, margin=0.05, min_samples=min_samples, strikes=2, promote_after=6)
    windows = 0
    while ctl.state == "running" and windows < 60:
        for _ in range(per_window or min_samples):
            ctl.observe("v1", float(rnd.random() < STABLE_Q))
            ctl.observe("v2", float(rnd.random() < canary_q))
        ctl.check()
        windows += 1
    return ctl.state, windows


print("Canary controller, margin 0.05, two strikes, 6 good windows to promote. 2000 trials each.")
print(f"{'min samples per arm':>20}{'good canary rolled back':>25}{'bad canary caught':>19}{'windows to catch':>18}")
for n in (30, 100, 300, 1000):
    good = sum(trial(GOOD_Q, n, s)[0] == "rolled_back" for s in range(2000)) / 2000
    bad = [trial(BAD_Q, n, 10_000 + s) for s in range(2000)]
    caught = sum(x[0] == "rolled_back" for x in bad) / 2000
    mean_w = sum(x[1] for x in bad if x[0] == "rolled_back") / max(1, sum(x[0] == "rolled_back" for x in bad))
    print(f"{n:>20}{good:>25.1%}{caught:>19.1%}{mean_w:>18.1f}")

print("\nOne day with 20,000 requests, canary share 10%, judge scores 20% of requests, 100 scores per arm per window, bad canary quality 0.62:")
rnd = random.Random(7)
router = CanaryRouter(percent=10)
ctl = RollbackController(router, min_samples=100)
users = [f"user-{i}" for i in range(1500)]
served = {"v1": 0, "v2": 0}
bad_answers = 0
rolled_at = None
for i in range(20000):
    version = router.route(rnd.choice(users))
    served[version] += 1
    good = rnd.random() < (STABLE_Q if version == "v1" else BAD_Q)
    bad_answers += (not good)
    if rnd.random() < 0.2:
        ctl.observe(version, float(good))
    if i % 500 == 499 and ctl.check() == "rolled_back" and rolled_at is None:
        rolled_at = i + 1
print("rolled back after request:", rolled_at, "| requests served by v2:", served["v2"], "| bad answers in the day:", bad_answers)
print("expected bad answers if everyone stayed on v1:", round(20000 * (1 - STABLE_Q)), "| if v2 had shipped to everyone:", round(20000 * (1 - BAD_Q)))
