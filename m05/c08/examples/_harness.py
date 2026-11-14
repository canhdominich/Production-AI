import contextlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
PLATFORM = HERE.parents[1] / "platform"
OUT = Path("/tmp/m05c08-run")
PORTS = {"provider": 5680, "api": 5681, "tools": 5682, "redis": 5683}


def wait(url):
    for _ in range(300):
        try:
            if httpx.get(url, timeout=0.5).status_code == 200:
                return
        except httpx.TransportError:
            time.sleep(0.05)
    raise RuntimeError("service did not start: " + url)


@contextlib.contextmanager
def stack(**env):
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    base = dict(os.environ, TRACE_OUT=str(OUT), FAKE_SEED="42", FAKE_TIME_SCALE="0.1", PYTHONPATH=str(HERE), **{k: str(v) for k, v in env.items()})
    procs = [subprocess.Popen([sys.executable, str(PLATFORM / "fake_provider.py"), "--port", str(PORTS["provider"])], env=base, cwd=str(PLATFORM),
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)]
    for name in ("tools", "api"):
        procs.append(subprocess.Popen([sys.executable, str(HERE / "_services.py"), name, "--port", str(PORTS[name])], env=base, cwd=str(HERE),
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    try:
        wait(f"http://127.0.0.1:{PORTS['provider']}/health")
        wait(f"http://127.0.0.1:{PORTS['tools']}/health")
        wait(f"http://127.0.0.1:{PORTS['api']}/health")
        yield OUT
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            p.wait(timeout=5)


def read_jsonl(path):
    path = Path(path)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def load_spans(out=OUT):
    return [s for f in sorted(Path(out).glob("*.spans.jsonl")) for s in read_jsonl(f)]


def load_logs(out=OUT):
    return {f.name.split(".")[0]: read_jsonl(f) for f in sorted(Path(out).glob("*.log.jsonl"))}


def print_tree(spans, root_parent=None):
    ids = {s["span_id"] for s in spans}
    kids = {}
    for s in sorted(spans, key=lambda s: s["start_ns"]):
        kids.setdefault(s["parent_id"] if s["parent_id"] in ids else root_parent, []).append(s)

    def walk(parent, depth):
        for s in kids.get(parent, []):
            print(f"{'  ' * depth}{s['name']:<{34 - 2 * depth}}{s['service']:<6}{s['kind']}")
            walk(s["span_id"], depth + 1)
    walk(root_parent, 0)


@contextlib.contextmanager
def redis_server(port):
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
