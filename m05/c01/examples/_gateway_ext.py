import random
import threading
import time

from _harness import PLATFORM
from gateway_core import Gateway, GatewayError, ProviderError


class TenantRateLimited(GatewayError):
    status = 429


class BudgetExceeded(GatewayError):
    status = 402


class ProviderUnavailable(GatewayError):
    status = 503


class TokenBucket:
    def __init__(self, rate_per_s, burst):
        self.rate, self.burst = rate_per_s, burst
        self.tokens, self.last = float(burst), time.monotonic()
        self.lock = threading.Lock()

    def take(self):
        with self.lock:
            now = time.monotonic()
            self.tokens = min(self.burst, self.tokens + (now - self.last) * self.rate)
            self.last = now
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False


class GatewayV1(Gateway):
    def __init__(self, providers, max_concurrency=8, max_attempts=3, time_scale=1.0, **kw):
        super().__init__(providers, **kw)
        self.slots = threading.BoundedSemaphore(max_concurrency)
        self.max_attempts, self.time_scale = max_attempts, time_scale
        self.buckets = {t.tenant_id: TokenBucket(t.rate_limit_rpm / 60 / time_scale, max(5, t.rate_limit_rpm // 10)) for t in self.tenants.all()}
        self.rnd = random.Random(0)

    def choose_provider(self, req, attempt=0):
        return self.providers[attempt % len(self.providers)]

    def check_limits(self, tenant):
        if not self.buckets[tenant.tenant_id].take():
            raise TenantRateLimited(f"{tenant.tenant_id} is over {tenant.rate_limit_rpm} requests per minute")
        if self.sink.total_cost(tenant_id=tenant.tenant_id) >= tenant.monthly_budget_usd:
            raise BudgetExceeded(f"{tenant.tenant_id} used its monthly budget of {tenant.monthly_budget_usd} USD")

    def pause(self, error, attempt):
        wait = error.retry_after if error.kind == "rate_limit" and error.retry_after else min(0.2 * 2 ** attempt, 2.0) * (0.5 + self.rnd.random())
        time.sleep(wait * self.time_scale)

    def handle(self, req):
        tenant = self.tenants.get(req.tenant_id)
        self.before_call(req, tenant)
        self.check_limits(tenant)
        model = self.prices.model_for(req.tier)
        started = time.perf_counter()
        last = None
        with self.slots:
            for attempt in range(self.max_attempts):
                provider = self.choose_provider(req, attempt)
                try:
                    result = self.call_provider(provider, model, req)
                except ProviderError as e:
                    last = e
                    self.record_failure(req, provider, model, e, started, attempts=attempt + 1)
                    if e.kind == "bad_request":
                        break
                    self.pause(e, attempt)
                    continue
                return self.finish(req, provider, model, result, started, attempts=attempt + 1, fallback_used=provider is not self.providers[0])
        raise ProviderUnavailable(f"all attempts failed, last error: {last}")
