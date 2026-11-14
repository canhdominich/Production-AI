import time

import httpx

from _dock import API, compose, ps, wait_api

compose("down", "-v", "--remove-orphans")
t0 = time.perf_counter()
compose("up", "-d", "--wait")
print(f"docker compose up -d --wait finished in {time.perf_counter() - t0:.1f} s")
print(f"{'service':<10}{'state':<10}{'health':<10}exit")
for svc, (state, health, code) in sorted(ps().items()):
    print(f"{svc:<10}{state:<10}{health:<10}{code}")

wait_api()
with httpx.Client(base_url=API, timeout=30) as c:
    for i in range(3):
        c.post("/chat", json={"tenant_id": "br-cau-go", "text": f"Don AT10{i} da den chua?"}).raise_for_status()
    job = c.post("/reports", json={"tenant_id": "br-cau-go", "week": "2026-W45"}).json()
    print("POST /reports ->", job)
    for _ in range(40):
        status = c.get(f"/jobs/{job['job_id']}").json()["status"]
        if status == "done":
            break
        time.sleep(0.5)
    print("job status:", status)
    print("GET /stats ->", c.get("/stats").json())
