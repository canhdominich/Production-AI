import random

import release_gate as rg

rnd = random.Random(7)


def scores(n, mean, sd):
    return [min(1.0, max(0.0, rnd.gauss(mean, sd))) for _ in range(n)]


users = [f"user-{i}" for i in range(2000)]
share = sum(rg.route(u, 10, "prompt-v2") == "canary" for u in users) / len(users)
print(f"canary share of 2000 users: {share:.1%}")

for name, mean, sd in [("good candidate", 0.83, 0.10), ("bad candidate", 0.68, 0.12)]:
    run = rg.CanaryRun(promote_after=6)
    window = 0
    while run.status == "running":
        window += 1
        run.step(scores(360, 0.82, 0.10), scores(40, mean, sd))
    print(f"{name}: {run.status} after {window} windows, history {run.history}")
