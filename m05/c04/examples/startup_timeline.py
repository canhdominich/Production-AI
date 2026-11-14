import json
import os
import signal
import subprocess
import time
from datetime import datetime

from _dock import STACK, TMP, compose

compose("down", "-v", "--remove-orphans")
log = TMP / "events.jsonl"
out = open(log, "w")
events = subprocess.Popen(["docker", "compose", "-f", str(STACK / "compose.yaml"), "events", "--json"], stdout=out, start_new_session=True)
time.sleep(1)
compose("up", "-d", "--wait")
time.sleep(2)
os.killpg(events.pid, signal.SIGTERM)
events.wait()
out.close()
rows = []
for line in log.read_text().splitlines():
    e = json.loads(line)
    rows.append((datetime.fromisoformat(e["time"][:26]).timestamp(), e["service"], e["action"]))
rows.sort()
t0 = min(t for t, svc, a in rows if a == "start")
keep = ("start", "health_status: healthy", "die")
print(f"{'seconds':>8}  {'service':<9} event")
for t, svc, action in rows:
    if action in keep:
        print(f"{t - t0:>8.1f}  {svc:<9} {action.replace('health_status: ', '')}")
compose("down", "-v", "--remove-orphans")
