"""Minimal AI gateway skeleton for m05. Later chapters subclass or wrap these classes; they never edit this file.

Pieces: ProviderClient (talk to an OpenAI-compatible endpoint), UsageRecord (one row per model call),
TenantRegistry (who is calling), PriceTable (what a call costs) and Gateway (the single entry point).
The skeleton has no rate limit, no budget check, no retry and no fallback on purpose: those are the
extension points (before_call, call_provider, on_error, choose_provider) that chapters 1, 10, 11 and 13 fill in.
"""
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

import httpx

from common import DATA_DIR, FEATURES, TIER_RANK, estimate_prompt_tokens


class GatewayError(Exception):
    status = 500


class UnknownTenant(GatewayError):
    status = 401


class FeatureNotAllowed(GatewayError):
    status = 403


class ProviderError(GatewayError):
    def __init__(self, kind, status_code=None, retry_after=None, message=""):
        super().__init__(f"{kind} ({status_code}) {message}".strip())
        self.kind = kind
        self.status_code = status_code
        self.retry_after = retry_after


@dataclass
class Tenant:
    tenant_id: str
    name: str
    plan: str
    monthly_budget_usd: float
    rate_limit_rpm: int
    allowed_features: list
    max_tier: str
    api_key: str
    users: list = field(default_factory=list)


class TenantRegistry:
    def __init__(self, path=None):
        data = json.loads(Path(path or DATA_DIR / "tenants.json").read_text(encoding="utf-8"))
        self.roles = data["roles"]
        self.budget_policy = data["budget_policy"]
        self._by_id = {}
        for t in data["tenants"]:
            self._by_id[t["tenant_id"]] = Tenant(**{k: t[k] for k in Tenant.__dataclass_fields__})
        self._by_key = {t.api_key: t for t in self._by_id.values()}

    def get(self, tenant_id):
        try:
            return self._by_id[tenant_id]
        except KeyError:
            raise UnknownTenant(f"unknown tenant {tenant_id!r}") from None

    def by_api_key(self, key):
        try:
            return self._by_key[key]
        except KeyError:
            raise UnknownTenant("unknown api key") from None

    def all(self):
        return list(self._by_id.values())

    def check_feature(self, tenant, feature, role=None):
        if feature not in FEATURES:
            raise FeatureNotAllowed(f"unknown feature {feature!r}")
        if feature not in tenant.allowed_features:
            raise FeatureNotAllowed(f"tenant {tenant.tenant_id} does not have {feature}")
        if role is not None and feature not in self.roles[role]["features"]:
            raise FeatureNotAllowed(f"role {role} cannot use {feature}")


class PriceTable:
    def __init__(self, path=None):
        data = json.loads(Path(path or DATA_DIR / "prices.json").read_text(encoding="utf-8"))
        self.illustrative = data["illustrative"]
        self.tiers = data["tiers"]
        self.models = data["models"]

    def model_for(self, tier):
        return self.tiers[tier]

    def tier_of(self, model):
        return self.models[model]["tier"]

    def cost(self, model, prompt_tokens, output_tokens, cached_tokens=0):
        p = self.models[model]
        fresh = max(0, prompt_tokens - cached_tokens)
        return (fresh * p["input_per_mtok"] + cached_tokens * p["cached_input_per_mtok"] + output_tokens * p["output_per_mtok"]) / 1_000_000


@dataclass
class UsageRecord:
    request_id: str
    tenant_id: str
    feature: str
    model: str
    provider: str
    status: str
    prompt_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float = 0.0
    ttft_ms: float = 0.0
    latency_ms: float = 0.0
    attempts: int = 1
    fallback_used: bool = False
    error_kind: str = ""
    role: str = ""
    ts: float = 0.0

    def as_dict(self):
        return asdict(self)


class UsageSink:
    def __init__(self):
        self.records = []

    def write(self, record):
        self.records.append(record)

    def total_cost(self, **where):
        return sum(r.cost_usd for r in self.records if all(getattr(r, k) == v for k, v in where.items()))

    def to_jsonl(self, path):
        Path(path).write_text("".join(json.dumps(r.as_dict(), ensure_ascii=False) + "\n" for r in self.records), encoding="utf-8")


@dataclass
class ProviderResult:
    text: str
    prompt_tokens: int
    output_tokens: int
    ttft_s: float
    total_s: float
    finish_reason: str = "stop"
    status_code: int = 200


class ProviderClient:
    """Sync client for one OpenAI-compatible chat completions endpoint."""

    def __init__(self, name, base_url, api_key="demo", timeout_s=60.0):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_s = timeout_s
        self._http = httpx.Client(timeout=timeout_s)

    def close(self):
        self._http.close()

    def _headers(self, request_id, output_tokens):
        h = {"authorization": f"Bearer {self.api_key}", "x-fake-request-id": request_id}
        if output_tokens:
            h["x-fake-output-tokens"] = str(output_tokens)
        return h

    def _raise_for(self, r):
        if r.status_code == 200:
            return
        ra = r.headers.get("retry-after")
        kind = {429: "rate_limit", 400: "bad_request", 404: "bad_request"}.get(r.status_code, "server_error" if r.status_code >= 500 else "http_error")
        raise ProviderError(kind, r.status_code, float(ra) if ra else None, r.text[:120])

    def complete(self, model, messages, max_tokens=None, request_id=None, output_tokens=None, timeout_s=None):
        rid = request_id or uuid.uuid4().hex[:12]
        body = {"model": model, "messages": messages}
        if max_tokens:
            body["max_tokens"] = max_tokens
        t0 = time.perf_counter()
        try:
            r = self._http.post(f"{self.base_url}/v1/chat/completions", json=body, headers=self._headers(rid, output_tokens), timeout=timeout_s or self.timeout_s)
        except httpx.TimeoutException as e:
            raise ProviderError("timeout", None, None, str(e)) from None
        except httpx.TransportError as e:
            raise ProviderError("connection", None, None, str(e)) from None
        self._raise_for(r)
        total = time.perf_counter() - t0
        d = r.json()
        ch = d["choices"][0]
        return ProviderResult(ch["message"]["content"], d["usage"]["prompt_tokens"], d["usage"]["completion_tokens"], total, total, ch["finish_reason"])

    def stream(self, model, messages, max_tokens=None, request_id=None, output_tokens=None, timeout_s=None):
        """Yield (elapsed_seconds, text_piece); the last item is (elapsed, ProviderResult)."""
        rid = request_id or uuid.uuid4().hex[:12]
        body = {"model": model, "messages": messages, "stream": True, "stream_options": {"include_usage": True}}
        if max_tokens:
            body["max_tokens"] = max_tokens
        t0 = time.perf_counter()
        parts, ttft, usage, finish = [], None, None, "stop"
        try:
            with self._http.stream("POST", f"{self.base_url}/v1/chat/completions", json=body, headers=self._headers(rid, output_tokens), timeout=timeout_s or self.timeout_s) as r:
                if r.status_code != 200:
                    r.read()
                    self._raise_for(r)
                for line in r.iter_lines():
                    if not line.startswith("data: ") or line == "data: [DONE]":
                        continue
                    ev = json.loads(line[6:])
                    if ev.get("usage"):
                        usage = ev["usage"]
                    for c in ev.get("choices", []):
                        if c.get("finish_reason"):
                            finish = c["finish_reason"]
                        piece = c["delta"].get("content")
                        if piece:
                            now = time.perf_counter() - t0
                            ttft = ttft if ttft is not None else now
                            parts.append(piece)
                            yield now, piece
        except httpx.TimeoutException as e:
            raise ProviderError("timeout", None, None, str(e)) from None
        except httpx.TransportError as e:
            raise ProviderError("connection", None, None, str(e)) from None
        total = time.perf_counter() - t0
        usage = usage or {"prompt_tokens": 0, "completion_tokens": len(parts)}
        yield total, ProviderResult("".join(parts), usage["prompt_tokens"], usage["completion_tokens"], ttft or total, total, finish)


@dataclass
class GatewayRequest:
    tenant_id: str
    feature: str
    messages: list
    tier: str = "medium"
    role: str = ""
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    max_tokens: int = 0
    output_tokens: int = 0


@dataclass
class GatewayResponse:
    request_id: str
    text: str
    record: UsageRecord


class Gateway:
    """One entry point for every model call. Subclass and override the hooks to add behaviour."""

    def __init__(self, providers, tenants=None, prices=None, sink=None, clock=time.time):
        self.providers = providers
        self.tenants = tenants or TenantRegistry()
        self.prices = prices or PriceTable()
        self.sink = sink or UsageSink()
        self.clock = clock

    def choose_provider(self, req, attempt=0):
        return self.providers[0]

    def before_call(self, req, tenant):
        self.tenants.check_feature(tenant, req.feature, req.role or None)
        if TIER_RANK[req.tier] > TIER_RANK[tenant.max_tier]:
            req.tier = tenant.max_tier

    def call_provider(self, provider, model, req):
        return provider.complete(model, req.messages, req.max_tokens or None, req.request_id, req.output_tokens or None)

    def on_error(self, req, tenant, provider, error, started):
        raise error

    def handle(self, req):
        tenant = self.tenants.get(req.tenant_id)
        self.before_call(req, tenant)
        model = self.prices.model_for(req.tier)
        provider = self.choose_provider(req)
        started = time.perf_counter()
        try:
            result = self.call_provider(provider, model, req)
        except ProviderError as e:
            return self.on_error(req, tenant, provider, e, started)
        return self.finish(req, provider, model, result, started)

    def finish(self, req, provider, model, result, started, **extra):
        cost = self.prices.cost(model, result.prompt_tokens, result.output_tokens)
        rec = UsageRecord(req.request_id, req.tenant_id, req.feature, model, provider.name, "ok", result.prompt_tokens, result.output_tokens,
                          cost_usd=cost, ttft_ms=result.ttft_s * 1000, latency_ms=(time.perf_counter() - started) * 1000,
                          role=req.role, ts=self.clock(), **extra)
        self.sink.write(rec)
        return GatewayResponse(req.request_id, result.text, rec)

    def record_failure(self, req, provider, model, error, started, **extra):
        rec = UsageRecord(req.request_id, req.tenant_id, req.feature, model, provider.name, error.kind, 0, 0,
                          latency_ms=(time.perf_counter() - started) * 1000, error_kind=error.kind, role=req.role, ts=self.clock(), **extra)
        self.sink.write(rec)
        return rec
