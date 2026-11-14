import math
import random
import time
from dataclasses import dataclass, field

RETRYABLE = {"timeout", "rate_limit", "server_error", "connection"}


class ProviderFailure(Exception):
    def __init__(self, kind, status_code=None, retry_after=None):
        super().__init__(f"{kind} ({status_code})")
        self.kind = kind
        self.status_code = status_code
        self.retry_after = retry_after


class AllProvidersFailed(Exception):
    def __init__(self, attempts, reason="exhausted"):
        super().__init__(f"{reason} after {len(attempts)} attempts")
        self.attempts = attempts
        self.reason = reason


@dataclass
class CallResult:
    value: object
    provider: str
    attempts: int
    fallback_used: bool
    waited_s: float = 0.0
    log: list = field(default_factory=list)


def is_retryable(error):
    return getattr(error, "kind", None) in RETRYABLE


def backoff_delay(attempt, base=0.5, cap=8.0, jitter="full", rnd=None):
    ceiling = min(cap, base * 2 ** attempt)
    if jitter == "none":
        return ceiling
    return (rnd or random).random() * ceiling


def retry_wait(error, attempt, base=0.5, cap=8.0, rnd=None):
    hint = getattr(error, "retry_after", None)
    if getattr(error, "kind", None) == "rate_limit" and hint is not None:
        return hint + (rnd or random).random() * base
    return backoff_delay(attempt, base, cap, "full", rnd)


class CircuitBreaker:
    def __init__(self, failure_threshold=5, cooldown_s=30.0, half_open_max=1, clock=time.monotonic):
        self.failure_threshold = failure_threshold
        self.cooldown_s = cooldown_s
        self.half_open_max = half_open_max
        self.clock = clock
        self._state = "closed"
        self._failures = 0
        self._opened_at = 0.0
        self._probes = 0
        self.transitions = []

    def _move(self, state):
        self._state = state
        self.transitions.append((round(self.clock(), 3), state))

    @property
    def state(self):
        if self._state == "open" and self.clock() - self._opened_at >= self.cooldown_s:
            self._probes = 0
            self._move("half_open")
        return self._state

    def allow(self):
        state = self.state
        if state == "half_open" and self._probes < self.half_open_max:
            self._probes += 1
            return True
        return state == "closed"

    def record_success(self):
        if self.state == "half_open":
            self._failures = 0
            self._move("closed")
        elif self._state == "closed":
            self._failures = 0

    def record_failure(self):
        if self.state == "half_open":
            self._opened_at = self.clock()
            self._move("open")
        elif self._state == "closed":
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._opened_at = self.clock()
                self._move("open")

    @property
    def is_open(self):
        return self.state == "open"


class ResilientCaller:
    def __init__(self, providers, breakers=None, max_attempts=3, base=0.5, cap=8.0, deadline_s=20.0,
                 clock=time.monotonic, sleep=time.sleep, rnd=None):
        self.providers = providers
        self.breakers = breakers or {name: CircuitBreaker(clock=clock) for name, _ in providers}
        self.max_attempts = max_attempts
        self.base, self.cap, self.deadline_s = base, cap, deadline_s
        self.clock, self.sleep = clock, sleep
        self.rnd = rnd or random.Random(0)

    def call(self, request):
        start = self.clock()
        log, waited, calls = [], 0.0, 0
        first = self.providers[0][0]
        for name, fn in self.providers:
            breaker = self.breakers[name]
            for attempt in range(self.max_attempts):
                remaining = self.deadline_s - (self.clock() - start)
                if remaining <= 0:
                    raise AllProvidersFailed(log, "deadline")
                if not breaker.allow():
                    log.append((name, "circuit_open"))
                    break
                calls += 1
                try:
                    value = fn(request, remaining)
                except Exception as e:
                    if not hasattr(e, "kind"):
                        raise
                    log.append((name, e.kind))
                    if e.kind != "bad_request":
                        breaker.record_failure()
                    if not is_retryable(e):
                        raise
                    if attempt + 1 < self.max_attempts:
                        left = self.deadline_s - (self.clock() - start)
                        wait = retry_wait(e, attempt, self.base, self.cap, self.rnd)
                        if wait > self.cap:
                            log.append((name, "retry_after_too_long"))
                            break
                        wait = min(wait, max(0.0, left))
                        self.sleep(wait)
                        waited += wait
                    continue
                breaker.record_success()
                return CallResult(value, name, calls, name != first, waited, log)
        raise AllProvidersFailed(log)


def error_budget(slo, total_events):
    return math.floor(round(total_events * (1 - slo), 6))


def downtime_minutes(slo, days=30):
    return round(days * 24 * 60 * (1 - slo), 2)


def budget_status(slo, total_events, bad_events):
    allowed = error_budget(slo, total_events)
    return {"allowed": allowed, "bad": bad_events, "remaining": allowed - bad_events,
            "burned": round(bad_events / allowed, 4) if allowed else math.inf}


def compute_slis(records, latency_ms):
    counted = [r for r in records if r["status"] != "bad_request"]
    if not counted:
        raise ValueError("no countable records")
    ok = [r for r in counted if r["status"] == "ok"]
    fast = [r for r in ok if r["latency_ms"] <= latency_ms]
    whole = [r for r in ok if r.get("finish_reason", "stop") == "stop"]
    return {"availability": len(ok) / len(counted),
            "latency": len(fast) / len(ok) if ok else 0.0,
            "quality": len(whole) / len(ok) if ok else 0.0}
