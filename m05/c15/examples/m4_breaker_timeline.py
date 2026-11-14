import _kit  # noqa: F401
from anhti_platform.gateway import CircuitBreaker

now = [0.0]
b = CircuitBreaker(failure_threshold=3, cooldown_s=30.0, clock=lambda: now[0])
primary_down_until = 70.0
fails = 0
print(f"{'second':>7}  {'breaker':9} {'primary called':15} result")
for t in range(0, 130, 5):
    now[0] = float(t)
    state = b.state
    allowed = b.allow()
    if allowed:
        ok = t >= primary_down_until
        fails += (not ok)
        b.success() if ok else b.failure()
        result = "ok" if ok else "fail"
    else:
        result = "skipped, secondary serves"
    print(f"{t:>7}  {state:9} {str(allowed):15} {result}")
print("calls that reached the failing primary:", fails, "of", 70 // 5, "attempts while it was down")
