import time

import httpx

from _dock import API, compose, wait_api


def stats():
    wait_api()
    return httpx.get(f"{API}/stats", timeout=10).json()


compose("down", "-v", "--remove-orphans")
compose("up", "-d", "--wait")
wait_api()
with httpx.Client(base_url=API, timeout=30) as c:
    for i in range(4):
        c.post("/chat", json={"tenant_id": "br-cau-go", "text": f"Hoi so {i}"}).raise_for_status()
    ids = [c.post("/reports", json={"tenant_id": "br-cau-go", "week": f"2026-W4{i}"}).json()["job_id"] for i in range(2)]
    for _ in range(60):
        if c.get("/stats").json()["jobs"].get("done") == 2:
            break
        time.sleep(0.5)
print("1. before:                ", stats())

compose("restart")
compose("up", "-d", "--wait")
print("2. after compose restart: ", stats())

compose("down")
compose("up", "-d", "--wait")
print("3. after down then up:    ", stats())

compose("down", "-v")
compose("up", "-d", "--wait")
print("4. after down -v then up: ", stats())
compose("down", "-v", "--remove-orphans")
