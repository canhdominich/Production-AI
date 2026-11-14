import threading
import time
from concurrent.futures import ThreadPoolExecutor

import redis

from _kit import PORT_REDIS, redis_server
from _budget_lib import RedisBudget, budget_state

LIMIT = 0.05
ESTIMATE = 0.004
CLIENTS = 24
MONTH = "2026-10"


def naive(r, tenant):
    key = f"budget:{MONTH}:{tenant}"
    if float(r.get(key) or 0) >= LIMIT:
        return False
    gate.wait()
    r.incrbyfloat(key, ESTIMATE)
    return True


def atomic(budget, tenant):
    ok, _ = budget.reserve(tenant, ESTIMATE, LIMIT)
    if ok:
        time.sleep(0.02)
    return ok


gate = threading.Barrier(CLIENTS)


def run(fn, arg):
    with ThreadPoolExecutor(CLIENTS) as pool:
        return sum(pool.map(lambda _: fn(arg, "br-ben-song"), range(CLIENTS)))


with redis_server() as port:
    r = redis.Redis(port=port, protocol=2, decode_responses=True)
    print(f"budget left ${LIMIT}, each call estimated at ${ESTIMATE}, {CLIENTS} calls arrive together")
    print(f"at most {int(LIMIT / ESTIMATE)} calls fit\n")

    r.flushdb()
    admitted = run(naive, r)
    spent = float(r.get(f"budget:{MONTH}:br-ben-song"))
    print(f"read, check, call, write: {admitted} admitted, spent ${spent:.3f}, over budget by {spent / LIMIT - 1:.0%}")

    r.flushdb()
    budget = RedisBudget(r, MONTH)
    admitted = run(atomic, budget)
    spent = budget.spent("br-ben-song")
    print(f"one Lua script reserves:  {admitted} admitted, spent ${spent:.3f}, over budget by {max(0, spent / LIMIT - 1):.0%}")

    print("\nRedis restarts and loses its counters")
    r.flushdb()
    print(f"  counter after restart: ${budget.spent('br-ben-song'):.2f}, state: {budget_state(budget.spent('br-ben-song'), 60.0)}")
