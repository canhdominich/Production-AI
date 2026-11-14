from prometheus_client import CollectorRegistry, Counter, generate_latest

from _support import PLATFORM  # noqa: F401
from workload import generate

reqs = generate(5000, seed=42)
designs = {
    "tenant, feature": lambda r: (r.tenant_id, r.feature),
    "tenant, feature, model": lambda r: (r.tenant_id, r.feature, r.model),
    "tenant, feature, user_id": lambda r: (r.tenant_id, r.feature, r.user_id),
    "request_id": lambda r: (r.request_id,),
}
print(f"{'labels':28}{'series':>8}{'exposition bytes':>18}")
for name, key in designs.items():
    reg = CollectorRegistry()
    names = [f"l{i}" for i in range(len(key(reqs[0])))]
    c = Counter("llm_requests", "requests", names, registry=reg)
    for r in reqs:
        c.labels(*key(r)).inc()
    text = generate_latest(reg).decode()
    series = sum(1 for x in text.splitlines() if x.startswith("llm_requests_total"))
    print(f"{name:28}{series:>8}{len(text):>18}")
