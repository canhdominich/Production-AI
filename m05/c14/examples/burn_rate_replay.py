import numpy as np

from _kit import PLATFORM  # noqa: F401  (puts the shared platform on sys.path)
from workload import HOUR_WEIGHTS

BUDGET = 0.005
rng = np.random.default_rng(7)
per_minute = np.repeat(np.array(HOUR_WEIGHTS, dtype=float) / sum(HOUR_WEIGHTS) * 2000 / 60, 60)
total = rng.poisson(per_minute)
error_p = np.full(1440, 0.001)
INCIDENTS = {"blip 08:10, 2 min of failures": (490, 492, 1.0), "brownout 10:00 to 15:00, 5% failures": (600, 900, 0.05), "outage 19:00 to 19:20, 60% failures": (1140, 1160, 0.60)}
for start, end, p in INCIDENTS.values():
    error_p[start:end] = p
errors = rng.binomial(total, error_p)
ct, ce = np.concatenate([[0], np.cumsum(total)]), np.concatenate([[0], np.cumsum(errors)])


def ratio(minute, window):
    lo = max(0, minute + 1 - window)
    t = ct[minute + 1] - ct[lo]
    return (ce[minute + 1] - ce[lo]) / t if t else 0.0


def static_5m(m):
    return ratio(m, 5) > 0.05


def one_window(m):
    return ratio(m, 60) > 14.4 * BUDGET


def multi_window(m):
    return (ratio(m, 60) > 14.4 * BUDGET and ratio(m, 5) > 14.4 * BUDGET) or (ratio(m, 360) > 6 * BUDGET and ratio(m, 30) > 6 * BUDGET)


def episodes(rule):
    firing = [rule(m) for m in range(1440)]
    out, start = [], None
    for m, f in enumerate(firing + [False]):
        if f and start is None:
            start = m
        if not f and start is not None:
            out.append((start, m))
            start = None
    return out


def clock(m):
    return f"{m // 60:02d}:{m % 60:02d}"


print(f"one simulated day: {total.sum()} requests, {errors.sum()} failed, about {total.sum() * BUDGET:.0f} failures are the whole daily share of a 99.5% SLO")
for name, rule in (("static: 5 min error ratio over 5%", static_5m), ("one window: 1 h burn rate over 14.4", one_window), ("two windows: 1 h and 5 min, or 6 h and 30 min", multi_window)):
    eps = episodes(rule)
    print(f"\n{name}")
    print(f"  {len(eps)} firing episodes:", ", ".join(f"{clock(a)}-{clock(b)}" for a, b in eps[:8]) + (" ..." if len(eps) > 8 else ""))
    for label, (a, b, _) in INCIDENTS.items():
        inside = [(s0, e0) for s0, e0 in eps if a <= s0 <= b + 90]
        after = sum(rule(m) for m in range(b, b + 90))
        first = f"first alert {clock(inside[0][0])}, {inside[0][0] - a} min after the start" if inside else "no alert"
        print(f"  {label}: {first}; {len(inside)} separate alert(s); still firing {after} min after it ends")
    print(f"  episodes outside every incident: {sum(1 for s, e in eps if not any(a <= s <= b + 90 for a, b, _ in INCIDENTS.values()))}")
