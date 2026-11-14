import json
import threading
import time
import uuid

import httpx

from _harness import provider, redis_server

SCALE = 0.1
STEP_TOKENS = 350
crash = {"armed": True}


def submit(r, tenant, feature, idem_key):
    existing = r.get(f"idem:{idem_key}")
    if existing:
        return existing, False
    job_id = "job-" + uuid.uuid4().hex[:6]
    if not r.set(f"idem:{idem_key}", job_id, nx=True, ex=3600):
        return r.get(f"idem:{idem_key}"), False
    r.hset(f"job:{job_id}", mapping={"status": "queued", "tenant": tenant, "feature": feature, "attempts": 0, "progress": "0/4"})
    r.lpush("queue", job_id)
    return job_id, True


def worker(r, url, stop):
    with httpx.Client(timeout=30) as http:
        while not stop.is_set():
            item = r.brpop("queue", timeout=1)
            if not item:
                continue
            job_id = item[1]
            attempts = r.hincrby(f"job:{job_id}", "attempts", 1)
            r.hset(f"job:{job_id}", mapping={"status": "running", "progress": "0/4"})
            try:
                for step in range(1, 5):
                    if crash["armed"] and step == 3:
                        crash["armed"] = False
                        raise RuntimeError("worker process killed")
                    http.post(url + "/v1/chat/completions", json={"model": "fake-large", "messages": [{"role": "user", "content": f"step {step}"}]},
                              headers={"x-fake-output-tokens": str(STEP_TOKENS), "x-fake-request-id": f"{job_id}-a{attempts}-s{step}"})
                    r.hset(f"job:{job_id}", "progress", f"{step}/4")
                r.hset(f"job:{job_id}", mapping={"status": "done"})
            except RuntimeError:
                r.hset(f"job:{job_id}", "status", "retrying")
                r.lpush("queue", job_id)


with provider(5610, seed=42, time_scale=SCALE) as (url, cfg, app), redis_server(5611) as r:
    stop = threading.Event()
    t = threading.Thread(target=worker, args=(r, url, stop), daemon=True)
    t.start()
    t0 = time.perf_counter()
    job_id, created = submit(r, "br-cau-go", "weekly_report_agent", "cau-go-2026-W45")
    print(f"submit returned in {(time.perf_counter() - t0) * 1000:.1f} ms with {job_id}, new job: {created}")
    again, created2 = submit(r, "br-cau-go", "weekly_report_agent", "cau-go-2026-W45")
    print(f"same idempotency key again returns {again == job_id and 'the same job id' or again}, new job: {created2}")
    seen = []
    while True:
        h = r.hgetall(f"job:{job_id}")
        line = (h["status"], h["progress"], h["attempts"])
        if not seen or seen[-1] != line:
            seen.append(line)
            print(f"  t={(time.perf_counter() - t0) / SCALE:6.1f} s  status={h['status']:<8} progress={h['progress']}  attempts={h['attempts']}")
        if h["status"] == "done":
            break
        time.sleep(0.05)
    stop.set()
    stats = httpx.get(url + "/admin/stats").json()
    print(f"output tokens billed: {stats['output_tokens']}, tokens the report needed: {4 * STEP_TOKENS}")
