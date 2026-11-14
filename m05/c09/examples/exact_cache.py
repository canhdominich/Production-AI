import json
import time

import redis
from _toolkit import PORT_REDIS, cache_key, make_traffic, redis_server
from gateway_core import TenantRegistry

tenants = TenantRegistry()
ask = [{"role": "user", "content": "Kho của chi nhánh mình ở đâu?"}]
spaced = [{"role": "user", "content": "  Kho của chi nhánh   mình ở đâu?\n"}]
print("same text, extra spaces, same key:", cache_key("br-cau-go", "fake-small", ask) == cache_key("br-cau-go", "fake-small", spaced))
print("same text, other tenant, same key:", cache_key("br-cau-go", "fake-small", ask) == cache_key("br-ben-song", "fake-small", ask))
print("same text, other model, same key: ", cache_key("br-cau-go", "fake-small", ask) == cache_key("br-cau-go", "fake-large", ask))

with redis_server():
    r = redis.Redis(port=PORT_REDIS, decode_responses=True, protocol=2)

    shared = {}
    for t in ("br-cau-go", "br-ben-song"):
        k = cache_key(t, "fake-small", ask, scope_tenant=False)
        if k not in shared:
            shared[k] = f"Kho của {tenants.get(t).name} nằm ở đường số 3."
        print(f"[no tenant in key] {t:9} receives: {shared[k]}")

    r.set("demo", "x", ex=1)
    before = r.get("demo")
    time.sleep(1.2)
    print("ttl 1s:", before, "then", r.get("demo"))

    jobs = [j for j in make_traffic(1500, seed=42, duration_s=900) if j.req.feature == "chat"]
    cand = [j for j in jobs if j.cacheable]
    print(f"\nchat requests {len(jobs)}, first-turn and cacheable {len(cand)}, of which retyped {sum(j.variant for j in cand)}")
    for name, kw in (("tenant + model + text", {}), ("text only (unsafe)", {"scope_tenant": False})):
        r.flushdb()
        hits = cross = 0
        for j in cand:
            q = j.req
            key = cache_key(q.tenant_id, q.model, q.messages, q.max_tokens, **kw)
            got = r.get(key)
            if got:
                hits += 1
                cross += json.loads(got)["tenant"] != q.tenant_id
            else:
                r.set(key, json.dumps({"tenant": q.tenant_id}), ex=3600)
        print(f"{name:24} hits {hits:4} ({hits / len(cand):5.1%} of cacheable, {hits / len(jobs):5.1%} of chat), answers from another tenant: {cross}")
