import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "platform"))
import fake_provider
from gateway_core import PriceTable, ProviderClient
from workload import generate

PORT = 5720
cfg = fake_provider.Config(seed=42, time_scale=0.1)
server = uvicorn.Server(uvicorn.Config(fake_provider.create_app(cfg), host="127.0.0.1", port=PORT, log_level="error"))
threading.Thread(target=server.run, daemon=True).start()
while not server.started:
    time.sleep(0.05)

client = ProviderClient("fake", f"http://127.0.0.1:{PORT}")
prices = PriceTable()
V1 = "Bạn là trợ lý chăm sóc khách hàng. Trả lời ngắn gọn."
V2 = V1 + " Luôn nhắc mã đơn, nêu bước tiếp theo và hẹn thời gian xử lý cụ thể cho khách."
requests = [r for r in generate(200, seed=42) if r.feature == "chat"][:24]
shadow_rows = []


def with_prompt(r, system):
    return [{"role": "system", "content": system}] + [m for m in r.messages if m["role"] != "system"]


def shadow(r):
    res = client.complete("fake-medium", with_prompt(r, V2), request_id=r.request_id + "-shadow", output_tokens=170)
    shadow_rows.append((res.total_s, prices.cost("fake-medium", res.prompt_tokens, res.output_tokens)))


user_lat, stable_cost = [], 0.0
pool = ThreadPoolExecutor(max_workers=4)
for r in requests:
    t0 = time.perf_counter()
    res = client.complete("fake-medium", with_prompt(r, V1), request_id=r.request_id, output_tokens=120)
    user_lat.append(time.perf_counter() - t0)
    stable_cost += prices.cost("fake-medium", res.prompt_tokens, res.output_tokens)
    pool.submit(shadow, r)
pool.shutdown(wait=True)
server.should_exit = True

sh_cost = sum(c for _, c in shadow_rows)
print(f"requests: {len(requests)} (time_scale 0.1, latencies below are scaled back to real seconds)")
print(f"user latency p50 (stable only): {statistics.median(user_lat) * 10:.2f}s")
print(f"shadow latency p50: {statistics.median(t for t, _ in shadow_rows) * 10:.2f}s")
print(f"stable cost: ${stable_cost / len(requests) * 1000:.2f} per 1000 requests (illustrative prices)")
print(f"shadow cost: ${sh_cost / len(requests) * 1000:.2f} per 1000 requests, ratio {sh_cost / stable_cost:.2f}x")
print(f"extra spend while shadowing 100 percent: +{(sh_cost / stable_cost) * 100:.0f} percent")
print("quality verdict from this run: none (the fake provider text carries no meaning)")
