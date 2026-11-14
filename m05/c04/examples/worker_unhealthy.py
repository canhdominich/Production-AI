import json
import time

from _dock import compose, sh

compose("down", "-v", "--remove-orphans")
compose("up", "-d", "--wait")


def worker_state():
    cid = compose("ps", "-q", "worker").stdout.strip()
    d = json.loads(sh("docker", "inspect", cid).stdout)[0]
    return cid, d["State"]["Status"], d["State"]["Health"]["Status"], d["RestartCount"]


cid, status, health, restarts = worker_state()
print(f"t=  0 s  status={status:<8} health={health:<10} restarts={restarts}")
sh("docker", "kill", "--signal=SIGSTOP", cid)
t0 = time.time()
seen = set()
while time.time() - t0 < 90:
    time.sleep(5)
    _, status, health, restarts = worker_state()
    if health not in seen:
        seen.add(health)
        print(f"t={time.time() - t0:>3.0f} s  status={status:<8} health={health:<10} restarts={restarts}")
    if health == "unhealthy":
        break
sh("docker", "kill", "--signal=SIGCONT", cid)
for _ in range(20):
    time.sleep(3)
    _, status, health, restarts = worker_state()
    if health == "healthy":
        break
print(f"after SIGCONT, t={time.time() - t0:>3.0f} s  status={status:<8} health={health:<10} restarts={restarts}")
compose("down", "-v", "--remove-orphans")
