from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest

from _genai import ObservedGateway
from _support import provider
from gateway_core import GatewayRequest, ProviderClient
from workload import generate

reg = CollectorRegistry()
LAT = Histogram("llm_request_duration_seconds", "Gateway call duration", ["feature", "tier"], registry=reg,
                buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10))
TOK = Counter("llm_tokens_total", "Tokens by direction", ["feature", "direction"], registry=reg)
COST = Counter("llm_cost_usd_total", "Cost from the price table", ["tenant"], registry=reg)
FIN = Counter("llm_finish_total", "Finish reasons", ["feature", "reason"], registry=reg)

with provider(5672, time_scale=0.02) as url:
    gw = ObservedGateway([ProviderClient("fake", url)])
    for r in generate(60, seed=42):
        gr = GatewayRequest(r.tenant_id, r.feature, r.messages, r.tier, r.role, r.request_id, max_tokens=300, output_tokens=r.output_tokens)
        rec = gw.handle(gr).record
        LAT.labels(r.feature, r.tier).observe(rec.latency_ms / 1000)
        TOK.labels(r.feature, "input").inc(rec.prompt_tokens)
        TOK.labels(r.feature, "output").inc(rec.output_tokens)
        COST.labels(r.tenant_id).inc(rec.cost_usd)
        FIN.labels(r.feature, gr.finish_reason).inc()

text = generate_latest(reg).decode()
keep = [x for x in text.splitlines() if x.startswith(("llm_tokens_total", "llm_finish_total", "llm_cost_usd_total{")) or "feature=\"chat\",le=" in x and "tier=\"small\"" in x]
print("\n".join(keep[:22]))
print(f"... {len(text.splitlines())} lines in total, {len(text)} bytes")
