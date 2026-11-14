import contextlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
PLATFORM = str(BASE / "platform")
DATA = HERE.parent / "data"
if PLATFORM not in sys.path:
    sys.path.insert(0, PLATFORM)

import httpx


@contextlib.contextmanager
def provider(port, seed=42, time_scale=0.05, faults=None):
    env = dict(os.environ, FAKE_SEED=str(seed), FAKE_TIME_SCALE=str(time_scale))
    if faults:
        env["FAKE_FAULTS"] = json.dumps(faults)
    proc = subprocess.Popen([sys.executable, str(Path(PLATFORM) / "fake_provider.py"), "--port", str(port)], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=PLATFORM)
    url = f"http://127.0.0.1:{port}"
    for _ in range(300):
        try:
            if httpx.get(f"{url}/health", timeout=0.5).status_code == 200:
                break
        except httpx.TransportError:
            time.sleep(0.05)
    try:
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=5)
