import random
import time

from .base import Gateway, ProviderError, estimate_prompt_tokens
from .limits import RateLimited
from .telemetry import NullTelemetry
from .usage import month_key

RETRYABLE = {"rate_limit", "server_error", "timeout", "connection"}


class QuotaExceeded(Exception):
    status = 402


class AllProvidersFailed(Exception):
    status = 503

    def __init__(self, attempts):
        super().__init__(f"all providers failed after {attempts} attempts")
        self.attempts = attempts


def budget_state(spent, budget, soft_pct=80, hard_pct=100):
    # TODO 6: trả hard khi dùng từ hard_pct phần trăm ngân sách, soft từ soft_pct, ngược lại ok
    return "ok"


class CircuitBreaker:
    def __init__(self, failure_threshold=3, cooldown_s=30.0, clock=time.monotonic):
        self.failure_threshold = failure_threshold
        self.cooldown_s = cooldown_s
        self.clock = clock
        self.failures = 0
        self.opened_at = None
        self.probing = False

    @property
    def state(self):
        if self.opened_at is None:
            return "closed"
        return "half_open" if self.clock() - self.opened_at >= self.cooldown_s else "open"

    def allow(self):
        # TODO 7: closed thì cho; half_open thì cho đúng một lượt thăm dò; open thì chặn
        return True

    def success(self):
        self.failures, self.opened_at, self.probing = 0, None, False

    def failure(self):
        # TODO 8: tăng đếm lỗi, mở mạch khi đạt ngưỡng, bỏ cờ thăm dò
        return None


class PlatformGateway(Gateway):
    def __init__(self, providers, store, limiter, tenants=None, prices=None, clock=time.time, sleep=time.sleep, max_attempts=3,
                 backoff_base=0.2, backoff_cap=2.0, failure_threshold=3, cooldown_s=30.0, telemetry=None, rnd=None, mono=time.monotonic):
        super().__init__(providers, tenants, prices, None, clock)
        self.store, self.limiter, self.sleep = store, limiter, sleep
        self.max_attempts, self.backoff_base, self.backoff_cap = max_attempts, backoff_base, backoff_cap
        self.telemetry = telemetry or NullTelemetry()
        self.rnd = rnd or random.Random(7)
        self.breakers = {p.name: CircuitBreaker(failure_threshold, cooldown_s, mono) for p in providers}

    def before_call(self, req, tenant):
        super().before_call(req, tenant)
        allowed, retry_after = self.limiter.allow(tenant.tenant_id, tenant.rate_limit_rpm, self.clock())
        if not allowed:
            self.telemetry.block(tenant.tenant_id, "rate_limit")
            raise RateLimited(retry_after)
        spent = self.store.month_spend(tenant.tenant_id, month_key(self.clock()))
        policy = self.tenants.budget_policy
        state = budget_state(spent, tenant.monthly_budget_usd, policy["soft_limit_pct"], policy["hard_limit_pct"])
        if state == "soft":
            req.tier = "small"
        estimate = self.prices.cost(self.prices.model_for(req.tier), estimate_prompt_tokens(req.messages), req.max_tokens or 400)
        if state == "hard" or spent + estimate > tenant.monthly_budget_usd:
            self.telemetry.block(tenant.tenant_id, "quota")
            raise QuotaExceeded(f"monthly budget of {tenant.tenant_id} is used up")
        return state

    def pick_provider(self, failed):
        # TODO 9: ưu tiên provider chưa lỗi trong yêu cầu này và mạch cho phép; không có thì thử lại provider đã lỗi; không còn thì trả None
        return self.providers[0]

    def backoff(self, attempt, error):
        wait = self.rnd.uniform(0, min(self.backoff_cap, self.backoff_base * 2 ** attempt))
        if error.retry_after:
            wait = max(wait, min(error.retry_after, self.backoff_cap))
        return wait

    def handle(self, req, user_id="", prompt_version="v1"):
        tenant = self.tenants.get(req.tenant_id)
        with self.telemetry.span("gateway.handle", tenant_id=tenant.tenant_id, feature=req.feature, prompt_version=prompt_version):
            state = self.before_call(req, tenant)
            model = self.prices.model_for(req.tier)
            started = time.perf_counter()
            failed, last = set(), None
            for attempt in range(self.max_attempts):
                provider = self.pick_provider(failed)
                if provider is None:
                    break
                try:
                    with self.telemetry.span("provider.call", provider=provider.name, attempt=attempt + 1, model=model):
                        result = self.call_provider(provider, model, req)
                except ProviderError as e:
                    last = e
                    self.breakers[provider.name].failure()
                    failed.add(provider.name)
                    if e.kind not in RETRYABLE:
                        break
                    if attempt + 1 < self.max_attempts:
                        self.sleep(self.backoff(attempt, e))
                    continue
                self.breakers[provider.name].success()
                resp = self.finish(req, provider, model, result, started, attempts=attempt + 1,
                                   fallback_used=provider is not self.providers[0])
                self.emit(resp.record, user_id, prompt_version)
                resp.budget_state = state
                return resp
            rec = self.record_failure(req, provider or self.providers[0], model, last or ProviderError("unavailable"), started,
                                      attempts=attempt + 1)
            self.emit(rec, user_id, prompt_version)
            raise AllProvidersFailed(attempt + 1)

    def emit(self, rec, user_id, prompt_version):
        event = {**rec.as_dict(), "user_id": user_id, "prompt_version": prompt_version}
        self.store.add(event)
        self.telemetry.record(**event)
