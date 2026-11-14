import subprocess
import threading
import time
from pathlib import Path

import httpx
from prometheus_client import CollectorRegistry, Counter, Histogram, start_http_server

from _genai import ObservedGateway
from _support import provider
from gateway_core import GatewayRequest, ProviderClient
from workload import generate

STACK = Path(__file__).resolve().parents[1] / "stack"
PROM = "http://127.0.0.1:5670"


def compose(*args):
    return subprocess.run(["docker", "compose", "-f", str(STACK / "compose.yaml"), *args], capture_output=True, text=True)


def query(promql):
    r = httpx.get(f"{PROM}/api/v1/query", params={"query": promql}, timeout=10).json()
    return r["data"]["result"]


reg = CollectorRegistry()
LAT = Histogram("llm_request_duration_seconds", "Gateway call duration", ["feature"], registry=reg, buckets=(0.02, 0.05, 0.1, 0.25, 0.5, 1, 2.5))
TOK = Counter("llm_tokens_total", "Tokens by direction", ["feature", "direction"], registry=reg)
start_http_server(5674, registry=reg, addr="127.0.0.1")

up = compose("up", "-d")
try:
    for _ in range(60):
        try:
            if httpx.get(f"{PROM}/-/ready", timeout=1).status_code == 200:
                break
        except httpx.TransportError:
            time.sleep(0.5)
    reqs = generate(240, seed=42)
    with provider(5676, time_scale=0.02) as url:
        gw = ObservedGateway([ProviderClient("fake", url)])
        todo, lock = iter(reqs), threading.Lock()

        def worker():
            while True:
                with lock:
                    r = next(todo, None)
                if r is None:
                    return
                gr = GatewayRequest(r.tenant_id, r.feature, r.messages, r.tier, r.role, r.request_id, max_tokens=400, output_tokens=r.output_tokens)
                rec = gw.handle(gr).record
                LAT.labels(r.feature).observe(rec.latency_ms / 1000)
                TOK.labels(r.feature, "input").inc(rec.prompt_tokens)
                TOK.labels(r.feature, "output").inc(rec.output_tokens)
                time.sleep(0.05)

        threads = [threading.Thread(target=worker) for _ in range(3)]
        [t.start() for t in threads]
        [t.join() for t in threads]
    time.sleep(3)
    targets = httpx.get(f"{PROM}/api/v1/targets", timeout=5).json()["data"]["activeTargets"]
    print("Prometheus", httpx.get(f"{PROM}/api/v1/status/buildinfo", timeout=5).json()["data"]["version"])
    print("scrape target:", targets[0]["labels"]["job"], targets[0]["health"], "interval", targets[0]["scrapeInterval"])
    print("\nPromQL: sum by (feature) (llm_tokens_total{direction=\"output\"})")
    for x in sorted(query('sum by (feature) (llm_tokens_total{direction="output"})'), key=lambda x: x["metric"]["feature"]):
        print(f"   {x['metric']['feature']:22}{float(x['value'][1]):>8.0f}")
    print("\nPromQL: histogram_quantile(0.95, sum by (le, feature) (llm_request_duration_seconds_bucket)) in milliseconds")
    for x in sorted(query("histogram_quantile(0.95, sum by (le, feature) (llm_request_duration_seconds_bucket))"), key=lambda x: x["metric"]["feature"]):
        print(f"   {x['metric']['feature']:22}{float(x['value'][1]) * 1000:>8.0f}")
    print("\nPromQL: count({__name__=~\"llm_.*\"}) series stored:", query('count({__name__=~"llm_.*"})')[0]["value"][1])
finally:
    compose("down", "-v")
