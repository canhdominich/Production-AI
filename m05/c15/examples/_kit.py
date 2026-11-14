import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1]
PROJECT = LAB / "project-platform"
for p in (PROJECT / "solution", PROJECT / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

STACK_ENV = {
    "JWT_SECRET": "local-demo-secret-0123456789abcdef-0123456789",
    "KEY_PEPPER": "local-demo-pepper",
    "DEMO_PASSWORD": "local-demo-password",
    "POSTGRES_PASSWORD": "local-demo-db",
    "SITE_ADDRESS": "localhost",
    "HTTP_PORT": "5757",
    "HTTPS_PORT": "5758",
    "BREAKER_COOLDOWN_S": "8",
}
API = "http://127.0.0.1:5751"
PRIMARY_ADMIN = "http://127.0.0.1:5752"
SECONDARY_ADMIN = "http://127.0.0.1:5753"
PROM = "http://127.0.0.1:5756"
PG_DSN = "postgresql://anhti:local-demo-db@127.0.0.1:5754/anhti"

KEYS = {"br-dau-pho": "demo-key-dau-pho", "br-khu-cong-nghiep": "demo-key-khu-cong-nghiep", "br-cau-go": "demo-key-cau-go",
        "br-xom-vui": "demo-key-xom-vui", "br-ben-song": "demo-key-ben-song"}
SHARES = {"br-dau-pho": 0.30, "br-khu-cong-nghiep": 0.25, "br-cau-go": 0.18, "br-xom-vui": 0.17, "br-ben-song": 0.10}


def reset_stack_state():
    import httpx
    import redis
    redis.Redis(host="127.0.0.1", port=5755, protocol=2).flushdb()
    for url, faults in ((PRIMARY_ADMIN, {}), (SECONDARY_ADMIN, {})):
        httpx.post(url + "/admin/config", json={"faults": faults, "timeout_hang_s": 120.0})
        httpx.post(url + "/admin/reset")


def drive(plan, workers=48, timeout=40):
    """plan: list of (offset_seconds, tenant_id). Open loop: requests start on schedule whether or not earlier ones finished."""
    import time
    from concurrent.futures import ThreadPoolExecutor

    import httpx

    client = httpx.Client(base_url=API, timeout=timeout, limits=httpx.Limits(max_connections=workers))
    t0 = time.perf_counter()

    def one(item):
        offset, tenant = item
        wait = t0 + offset - time.perf_counter()
        if wait > 0:
            time.sleep(wait)
        s = time.perf_counter()
        r = client.post("/v1/chat", json={"message": "don at047838 bao gio toi"}, headers={"x-api-key": KEYS[tenant]})
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        return {"tenant": tenant, "status": r.status_code, "seconds": time.perf_counter() - s, "offset": offset,
                "provider": body.get("provider"), "attempts": body.get("attempts"), "fallback": body.get("fallback_used")}

    with ThreadPoolExecutor(workers) as pool:
        out = list(pool.map(one, plan))
    return out, time.perf_counter() - t0


def make_plan(rps, seconds, seed):
    import random
    rnd = random.Random(seed)
    tenants, weights = list(SHARES), list(SHARES.values())
    n = int(rps * seconds)
    return [(i / rps, rnd.choices(tenants, weights)[0]) for i in range(n)]


def pct(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int(p / 100 * len(values)))] if values else 0.0
