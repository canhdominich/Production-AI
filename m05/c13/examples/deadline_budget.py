import random

from _kit import AllProvidersFailed, CircuitBreaker, Clock, ProviderFailure, ResilientCaller

HEALTHY_S = 1.6


def run(label, per_try_s, max_attempts, deadline_s, a_open=False):
    clock = Clock()
    calls = {"a": 0, "b": 0}

    def hung_primary(request, remaining):
        calls["a"] += 1
        clock.t += min(per_try_s, remaining)
        raise ProviderFailure("timeout")

    def healthy_backup(request, remaining):
        calls["b"] += 1
        clock.t += HEALTHY_S
        return "answer"

    breakers = {"a": CircuitBreaker(5, 30.0, clock=clock), "b": CircuitBreaker(5, 30.0, clock=clock)}
    if a_open:
        for _ in range(5):
            breakers["a"].record_failure()
    caller = ResilientCaller([("a", hung_primary), ("b", healthy_backup)], breakers, max_attempts=max_attempts,
                             deadline_s=deadline_s, clock=clock, sleep=clock.sleep, rnd=random.Random(1))
    try:
        r = caller.call("req")
        outcome = f"answer from {r.provider}"
    except AllProvidersFailed as e:
        outcome = f"failed ({e.reason})"
    print(f"{label:<46} {outcome:<20} {clock.t:5.1f} s   a={calls['a']} b={calls['b']}")


print("primary hangs on every call; backup answers in 1.6 s; user deadline 20 s")
print(f"{"configuration":<46} {'result':<20} {'time':<7} calls")
run("per-try timeout 10 s, 3 attempts", 10.0, 3, 20.0)
run("per-try timeout 4 s, 2 attempts", 4.0, 2, 20.0)
run("per-try timeout 4 s, 2 attempts, breaker open", 4.0, 2, 20.0, a_open=True)
