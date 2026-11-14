import threading
import redis
from _sec import redis_server

LIMIT = 50
THREADS = 8
PER_THREAD = 20


def naive(r, key):
    n = int(r.get(key) or 0)
    if n < LIMIT:
        r.set(key, n + 1)
        return True
    return False


def atomic(r, key):
    return r.incr(key) <= LIMIT


def hammer(fn, r, key):
    out = []
    lock = threading.Lock()

    def work():
        local = [fn(r, key) for _ in range(PER_THREAD)]
        with lock:
            out.extend(local)
    ts = [threading.Thread(target=work) for _ in range(THREADS)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    return sum(out)


with redis_server() as port:
    r = redis.Redis(port=port, protocol=2)
    r.delete("a", "b")
    print(f"limit {LIMIT}, {THREADS * PER_THREAD} concurrent attempts")
    got = hammer(naive, r, "a")
    print("read then write :", got, "allowed")
    print("INCR            :", hammer(atomic, r, "b"), "allowed")
    assert got > LIMIT, "expected the race to let extra requests through"
