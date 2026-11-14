import random

from _kit import CircuitBreaker, Clock

REQUESTS, GAP_S, FLAKY = 2000, 0.5, 0.25


def flaky_run(threshold, cooldown_s):
    clock, rnd = Clock(), random.Random(11)
    breaker = CircuitBreaker(threshold, cooldown_s, clock=clock)
    served_by_b = 0
    for i in range(REQUESTS):
        clock.t = i * GAP_S
        if breaker.allow():
            if rnd.random() < FLAKY:
                breaker.record_failure()
                served_by_b += 1
            else:
                breaker.record_success()
        else:
            served_by_b += 1
    opens = sum(1 for _, s in breaker.transitions if s == "open")
    return opens, 100 * served_by_b / REQUESTS


print(f"A fails {FLAKY:.0%} of calls at random (no outage); {REQUESTS} requests; B always answers")
print(f"{'consecutive failures to open':<30} {'cooldown':>9} {'times opened':>13} {'answered by B':>14} {'failed calls before a real outage is cut':>42}")
for threshold, cooldown in ((2, 30), (3, 30), (5, 30), (8, 30), (5, 10)):
    opens, share = flaky_run(threshold, cooldown)
    print(f"{threshold:<30} {cooldown:>8}s {opens:>13} {share:>13.1f}% {threshold:>42}")
