import math

import numpy as np

DAYS, CHANGE = 14, 8
BASE_PASS, BASE_TOP = 0.80, 0.62
SCENARIOS = {
    "users ask differently": dict(psi=0.30, top=0.00, judge=0.00, probe=0.00),
    "documents changed": dict(psi=0.00, top=-0.09, judge=-0.20, probe=0.00),
    "provider updated model": dict(psi=0.00, top=0.00, judge=-0.18, probe=-0.28),
}


def simulate(effect, seed):
    rng = np.random.default_rng(seed)
    on = np.arange(1, DAYS + 1) >= CHANGE
    psi = np.abs(rng.normal(0.02, 0.01, DAYS)) + on * effect["psi"]
    top = rng.normal(BASE_TOP, 0.012, DAYS) + on * effect["top"]
    judge_n = np.full(DAYS, 40)
    judge = rng.binomial(judge_n, np.clip(BASE_PASS + on * effect["judge"], 0, 1))
    probe = rng.binomial(20, np.clip(0.90 + on * effect["probe"], 0, 1))
    return psi, top, judge, judge_n, probe


def first_alert(flags, strikes=2):
    run = 0
    for day, f in enumerate(flags, start=1):
        run = run + 1 if f else 0
        if run >= strikes:
            return day
    return None


def judge_flags(passed, n):
    out = []
    for i in range(len(passed)):
        lo = max(0, i - 2)
        k, m = passed[lo:i + 1].sum(), n[lo:i + 1].sum()
        out.append((k / m - BASE_PASS) / math.sqrt(BASE_PASS * (1 - BASE_PASS) / m) < -2.33)
    return out


print(f"change happens on day {CHANGE}; each cell is the first day a signal raised an alert, '-' means it stayed quiet")
print(f"{'cause':26}{'input PSI':>11}{'retrieval top1':>16}{'judge, 3 days':>15}{'probe set':>11}")
for seed, (name, effect) in enumerate(SCENARIOS.items(), start=1):
    psi, top, passed, n, probe = simulate(effect, seed)
    cells = [first_alert(psi > 0.25), first_alert(top < BASE_TOP - 0.05), first_alert(judge_flags(passed, n), 1), first_alert(probe <= 15)]
    print(f"{name:26}" + "".join(f"{(str(c) if c else '-'):>{w}}" for c, w in zip(cells, (11, 16, 15, 11))))
