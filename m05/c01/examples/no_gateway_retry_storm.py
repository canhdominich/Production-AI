import httpx
import threading

from _harness import provider
from gateway_core import GatewayRequest, ProviderClient
from _gateway_ext import GatewayV1

SCALE = 0.05
N = 60
MSG = [{"role": "user", "content": "Don AT123456 o dau?"}]


def naive_feature(url, i, outcome):
    http = httpx.Client(timeout=30)
    for attempt in range(5):
        r = http.post(url + "/v1/chat/completions", json={"model": "fake-small", "messages": MSG},
                      headers={"x-fake-request-id": f"d{i}-{attempt}", "x-fake-output-tokens": "100"})
        if r.status_code == 200:
            outcome[i] = "ok"
            return
    outcome[i] = "failed"


def via_gateway(gw, i, outcome):
    try:
        gw.handle(GatewayRequest("br-cau-go", "chat", MSG, tier="small", request_id=f"g{i}", output_tokens=100))
        outcome[i] = "ok"
    except Exception as e:
        outcome[i] = type(e).__name__


def burst(fn, *args):
    outcome = {}
    threads = [threading.Thread(target=fn, args=(*args, i, outcome)) for i in range(N)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return outcome


print(f"{N} chat requests arrive at once; the provider allows 6 requests in flight and answers 429 beyond that")
with provider(5610, seed=42, time_scale=SCALE, capacity=6, retry_after_s=1) as (url, cfg, app):
    out = burst(naive_feature, url)
    s = httpx.get(url + "/admin/stats").json()
    print(f"each feature retries 5 times at once : ok {list(out.values()).count('ok'):>2}/{N}, calls that reached the provider {s['requests']:>3}, 429 answers {s['status'].get('429', 0)}")

with provider(5610, seed=42, time_scale=SCALE, capacity=6, retry_after_s=1) as (url, cfg, app):
    gw = GatewayV1([ProviderClient("fake-a", url)], max_concurrency=6, time_scale=SCALE)
    for t in gw.tenants.all():
        gw.buckets[t.tenant_id].burst = 1000
        gw.buckets[t.tenant_id].tokens = 1000
    out = burst(via_gateway, gw)
    s = httpx.get(url + "/admin/stats").json()
    print(f"one gateway with 6 slots, backoff    : ok {list(out.values()).count('ok'):>2}/{N}, calls that reached the provider {s['requests']:>3}, 429 answers {s['status'].get('429', 0)}")
