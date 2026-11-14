import contextlib
import sys
import time
from pathlib import Path

PLATFORM = str(Path(__file__).resolve().parents[2] / "platform")
if PLATFORM not in sys.path:
    sys.path.insert(0, PLATFORM)

import httpx


@contextlib.contextmanager
def provider(port, **cfg):
    import json
    import os
    import subprocess

    env = dict(os.environ, FAKE_SEED=str(cfg.pop("seed", 42)), FAKE_TIME_SCALE=str(cfg.pop("time_scale", 1.0)))
    if "faults" in cfg:
        env["FAKE_FAULTS"] = json.dumps(cfg.pop("faults"))
    proc = subprocess.Popen([sys.executable, str(Path(PLATFORM) / "fake_provider.py"), "--port", str(port)], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=PLATFORM)
    url = f"http://127.0.0.1:{port}"
    for _ in range(200):
        try:
            if httpx.get(f"{url}/health", timeout=0.5).status_code == 200:
                break
        except httpx.TransportError:
            time.sleep(0.05)
    if cfg:
        httpx.post(f"{url}/admin/config", json=cfg)
    try:
        yield url, httpx.get(f"{url}/admin/config").json(), None
    finally:
        proc.terminate()
        proc.wait(timeout=5)


@contextlib.contextmanager
def redis_server(port):
    import subprocess

    import redis

    proc = subprocess.Popen(["redis-server", "--port", str(port), "--bind", "127.0.0.1", "--save", "", "--appendonly", "no"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    r = redis.Redis(host="127.0.0.1", port=port, decode_responses=True, protocol=2)
    try:
        for _ in range(100):
            try:
                r.ping()
                break
            except redis.ConnectionError:
                time.sleep(0.05)
        yield r
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def run_threads(fn, items, workers=12):
    import threading

    lock, it, out = threading.Lock(), iter(items), []

    def loop():
        while True:
            with lock:
                item = next(it, None)
            if item is None:
                return
            out.append(fn(item))

    threads = [threading.Thread(target=loop) for _ in range(workers)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return out
