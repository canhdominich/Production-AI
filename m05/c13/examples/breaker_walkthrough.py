from _kit import CircuitBreaker, Clock

clock = Clock()
breaker = CircuitBreaker(failure_threshold=3, cooldown_s=30, clock=clock)
events = [(0, "call fails"), (1, "call fails"), (2, "call succeeds"), (3, "call fails"), (4, "call fails"), (5, "call fails"),
          (6, "request arrives"), (20, "request arrives"), (35, "probe fails"), (40, "request arrives"), (66, "probe succeeds"), (67, "request arrives")]
print(f"{'time':>5}  {'event':<18} {'breaker lets it through':<24} state after")
for t, event in events:
    clock.t = t
    allowed = breaker.allow()
    if allowed and event in ("call fails", "probe fails"):
        breaker.record_failure()
    elif allowed and event in ("call succeeds", "probe succeeds"):
        breaker.record_success()
    print(f"{t:>4}s  {event:<18} {('yes' if allowed else 'no, fail fast'):<24} {breaker.state}")
