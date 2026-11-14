import hashlib
import math
import random
import statistics

SCORE_MODEL = {"stable": (0.82, 0.10), "good": (0.83, 0.10), "bad": (0.68, 0.12)}


def bucket(user_id, salt, buckets=100):
    digest = hashlib.sha256(f"{salt}:{user_id}".encode()).hexdigest()
    return int(digest[:8], 16) % buckets


def route(user_id, percent, salt="prompt-v2"):
    return "canary" if bucket(user_id, salt) < percent else "stable"


def scripted_score(kind, rnd):
    mean, sd = SCORE_MODEL[kind]
    return min(1.0, max(0.0, rnd.gauss(mean, sd)))


def welch(a, b):
    if len(a) < 2 or len(b) < 2:
        return 0.0
    se = math.sqrt(statistics.variance(a) / len(a) + statistics.variance(b) / len(b))
    return (statistics.mean(a) - statistics.mean(b)) / se if se else 0.0


class Controller:
    def __init__(self, margin=0.05, z=2.33, min_samples=30, strikes=2):
        self.margin, self.z, self.min_samples, self.strikes = margin, z, min_samples, strikes
        self.bad_windows = 0

    def observe(self, stable, canary):
        if len(canary) < self.min_samples:
            return "wait", f"only {len(canary)} canary scores"
        diff = statistics.mean(canary) - statistics.mean(stable)
        t = welch(canary, stable)
        if diff < -self.margin and t < -self.z:
            self.bad_windows += 1
            if self.bad_windows >= self.strikes:
                return "rollback", f"diff {diff:+.3f}, t {t:.1f}, {self.bad_windows} bad windows"
            return "watch", f"diff {diff:+.3f}, t {t:.1f}, first bad window"
        self.bad_windows = 0
        return "ok", f"diff {diff:+.3f}, t {t:.1f}"


def run_canary(candidate, percent=10, windows=8, window_size=400, seed=7, controller=None, users=2000):
    rnd = random.Random(seed)
    ctl = controller or Controller()
    served_canary = 0
    log = []
    for w in range(1, windows + 1):
        st, ca = [], []
        for _ in range(window_size):
            uid = f"user-{rnd.randrange(users)}"
            side = route(uid, percent)
            (ca if side == "canary" else st).append(scripted_score(candidate if side == "canary" else "stable", rnd))
        served_canary += len(ca)
        action, why = ctl.observe(st, ca)
        log.append((w, len(st), len(ca), statistics.mean(st), statistics.mean(ca) if ca else float("nan"), action, why))
        if action == "rollback":
            break
    return log, served_canary
