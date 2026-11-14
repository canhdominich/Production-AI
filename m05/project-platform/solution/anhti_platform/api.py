import hmac
import os
import time
import uuid
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from .auth import ApiKeyStore, AuthError, Forbidden, authorize_feature, authorize_usage_read, issue_token, known_user, verify_token
from .base import FeatureNotAllowed, GatewayRequest, ProviderClient, TenantRegistry, UnknownTenant
from .canary import CanaryRouter, RollbackController
from .config import Settings
from .gateway import AllProvidersFailed, PlatformGateway, QuotaExceeded
from .limits import RateLimited, RedisWindowLimiter, SlidingWindowLimiter
from .safelog import get_logger, log_event
from .telemetry import JsonlSpanExporter, Telemetry
from .usage import MemoryUsageStore, PgUsageStore, month_key


class LoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str
    password: str


class ChatBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    feature: Literal["chat", "knowledge_assistant", "weekly_report_agent"] = "chat"
    message: str = Field(min_length=1, max_length=4000)
    tier: Literal["small", "medium", "large"] = "medium"


def create_app(settings, providers, store=None, limiter=None, telemetry=None, router=None, clock=time.time, sleep=time.sleep):
    registry = TenantRegistry()
    store = store or MemoryUsageStore()
    telemetry = telemetry or Telemetry()
    router = router or CanaryRouter(percent=settings.canary_percent)
    gateway = PlatformGateway(providers, store, limiter or SlidingWindowLimiter(), registry, clock=clock, sleep=sleep, telemetry=telemetry,
                              cooldown_s=settings.breaker_cooldown_s)
    keys = ApiKeyStore(registry, settings.key_pepper)
    controller = RollbackController(router)
    averages = {}

    def report_quality(version, score):
        averages[version] = 0.9 * averages.get(version, score) + 0.1 * score
        telemetry.quality.labels(version).set(averages[version])
        controller.observe(version, score)
        return controller.check()

    log = get_logger()
    app = FastAPI(title="Anhti AI platform", version="1.0.0")
    app.state.gateway, app.state.store, app.state.telemetry, app.state.router = gateway, store, telemetry, router
    app.state.controller, app.state.report_quality = controller, report_quality

    def error(status, code, message, headers=None):
        return JSONResponse({"error": {"code": code, "message": message}}, status_code=status, headers=headers)

    @app.exception_handler(AuthError)
    async def _auth(_, e):
        return error(401, "unauthenticated", "Authentication failed", {"www-authenticate": "Bearer"})

    @app.exception_handler(Forbidden)
    async def _forbidden(_, e):
        return error(403, "forbidden", "This role cannot do that")

    @app.exception_handler(FeatureNotAllowed)
    async def _feature(_, e):
        return error(403, "forbidden", "This role or branch cannot use that feature")

    @app.exception_handler(UnknownTenant)
    async def _tenant(_, e):
        return error(401, "unauthenticated", "Authentication failed")

    @app.exception_handler(RateLimited)
    async def _rate(_, e):
        return error(429, "rate_limited", "Too many requests", {"retry-after": str(int(e.retry_after))})

    @app.exception_handler(QuotaExceeded)
    async def _quota(_, e):
        return error(402, "quota_exceeded", "The monthly budget of this branch is used up")

    @app.exception_handler(AllProvidersFailed)
    async def _down(_, e):
        return error(503, "provider_unavailable", "The model is temporarily unavailable", {"retry-after": "5"})

    @app.exception_handler(Exception)
    async def _unexpected(_, e):
        return error(500, "internal_error", "Unexpected error, see the request id in the logs")

    def principal(authorization: str | None = Header(None), x_api_key: str | None = Header(None)):
        if authorization and authorization.lower().startswith("bearer "):
            return known_user(registry, verify_token(settings.jwt_secret, authorization[7:].strip(), clock()))
        if x_api_key:
            return keys.verify(x_api_key)
        raise AuthError("missing credentials")

    @app.post("/auth/token")
    def login(body: LoginBody):
        for t in registry.all():
            for u in t.users:
                if u["user_id"] == body.user_id and hmac.compare_digest(body.password, settings.demo_password):
                    return {"access_token": issue_token(settings.jwt_secret, t.tenant_id, u["user_id"], u["role"], clock(), settings.token_ttl_s),
                            "token_type": "bearer", "expires_in": settings.token_ttl_s}
        raise AuthError("bad login")

    @app.post("/v1/chat")
    def chat(body: ChatBody, request: Request, p=Depends(principal)):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        authorize_feature(registry, p, body.feature)
        version = router.route(p.user_id)
        messages = [{"role": "system", "content": router.prompt_for(version)}, {"role": "user", "content": body.message}]
        req = GatewayRequest(p.tenant_id, body.feature, messages, body.tier, p.role, request_id=request_id, max_tokens=300)
        started = time.perf_counter()
        status = "ok"
        try:
            with telemetry.span("api.request", tenant_id=p.tenant_id, feature=body.feature, request_id=request_id):
                resp = gateway.handle(req, user_id=p.user_id, prompt_version=version)
        except Exception as e:
            status = type(e).__name__
            raise
        finally:
            log_event(log, "chat", request_id=request_id, tenant_id=p.tenant_id, role=p.role, feature=body.feature, status=status,
                      prompt_chars=len(body.message), latency_ms=round((time.perf_counter() - started) * 1000, 1))
        r = resp.record
        return JSONResponse({"request_id": request_id, "text": resp.text, "model": r.model, "provider": r.provider,
                             "prompt_version": version, "cost_usd": r.cost_usd, "attempts": r.attempts,
                             "fallback_used": r.fallback_used, "budget_state": resp.budget_state},
                            headers={"x-request-id": request_id})

    @app.get("/v1/usage")
    def own_usage(p=Depends(principal)):
        authorize_usage_read(p)
        return store.summary(p.tenant_id, month_key(clock()))

    @app.get("/v1/usage/{tenant_id}")
    def tenant_usage(tenant_id: str, p=Depends(principal)):
        authorize_usage_read(p)
        if tenant_id != p.tenant_id:
            raise HTTPException(404, "not found")
        return store.summary(tenant_id, month_key(clock()))

    @app.get("/metrics")
    def metrics():
        return Response(telemetry.render(), media_type="text/plain; version=0.0.4")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    return app


def build_app_from_env():
    settings = Settings.from_env()
    providers = [ProviderClient("primary", settings.primary_url, timeout_s=float(os.environ.get("PROVIDER_TIMEOUT_S", "20"))),
                 ProviderClient("secondary", settings.secondary_url, timeout_s=float(os.environ.get("PROVIDER_TIMEOUT_S", "20")))]
    store = PgUsageStore(settings.database_url) if settings.database_url else MemoryUsageStore()
    limiter = None
    if settings.redis_url:
        import redis
        limiter = RedisWindowLimiter(redis.Redis.from_url(settings.redis_url, protocol=2))
    exporter = JsonlSpanExporter(os.environ["TRACE_FILE"]) if os.environ.get("TRACE_FILE") else None
    return create_app(settings, providers, store=store, limiter=limiter, telemetry=Telemetry(exporter))
