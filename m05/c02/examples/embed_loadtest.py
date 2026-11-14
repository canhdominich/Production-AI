import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
from openai import OpenAI

import _paths  # noqa: F401
from common import percentile

HERE = Path(__file__).resolve().parent
TEXTS = [f"query: Đơn AT{100000 + i} của chi nhánh {['Cầu Gỗ', 'Bến Sông', 'Xóm Vui', 'Đầu Phố'][i % 4]} giao trễ bao lâu rồi?" for i in range(96)]
PORT = 5621


def serve(max_batch, wait_ms):
    proc = subprocess.Popen([sys.executable, str(HERE / "_embed_server.py"), "--port", str(PORT), "--max-batch", str(max_batch), "--wait-ms", str(wait_ms)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=HERE)
    for _ in range(600):
        try:
            if httpx.get(f"http://127.0.0.1:{PORT}/health", timeout=0.5).status_code == 200:
                return proc
        except httpx.TransportError:
            time.sleep(0.1)
    raise RuntimeError("server did not start")


def load(clients):
    http = OpenAI(base_url=f"http://127.0.0.1:{PORT}/v1", api_key="none", max_retries=0)
    http.embeddings.create(model="intfloat/multilingual-e5-small", input=TEXTS[0])
    it, lock, lat = iter(TEXTS), threading.Lock(), []

    def worker():
        while True:
            with lock:
                text = next(it, None)
            if text is None:
                return
            t0 = time.perf_counter()
            http.embeddings.create(model="intfloat/multilingual-e5-small", input=text)
            lat.append(time.perf_counter() - t0)

    t0 = time.perf_counter()
    threads = [threading.Thread(target=worker) for _ in range(clients)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    wall = time.perf_counter() - t0
    stats = httpx.get(f"http://127.0.0.1:{PORT}/stats").json()
    return wall, lat, stats


print("max_batch wait_ms clients   requests/s   p50 ms   p95 ms   model calls   mean batch")
for max_batch, wait_ms, clients in ((1, 0, 1), (1, 0, 16), (32, 5, 16)):
    proc = serve(max_batch, wait_ms)
    try:
        wall, lat, stats = load(clients)
    finally:
        proc.terminate()
        proc.wait(timeout=10)
    print(f"{max_batch:>9} {wait_ms:>7} {clients:>7} {len(TEXTS) / wall:12.1f} {statistics.median(lat) * 1000:8.0f} {percentile(lat, 95) * 1000:8.0f} {stats['model_calls'] - 1:>13} {stats['mean_batch']:>12.1f}")
