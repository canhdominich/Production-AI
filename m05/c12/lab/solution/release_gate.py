import hashlib
import math
import statistics
from pathlib import Path

REQUIRED_SECTIONS = ["identity", "intended_use", "out_of_scope", "data_sources", "evaluation", "limitations", "oversight", "config_digest"]
HONEST_LABELS = ("Đã chạy", "Minh họa")


def bucket(user_id, salt, buckets=100):
    digest = hashlib.sha256(f"{salt}:{user_id}".encode()).hexdigest()
    return int(digest[:8], 16) % buckets


def route(user_id, percent, salt="release"):
    return "canary" if bucket(user_id, salt) < percent else "stable"


def welch_t(a, b):
    if len(a) < 2 or len(b) < 2:
        return 0.0
    se = math.sqrt(statistics.variance(a) / len(a) + statistics.variance(b) / len(b))
    if se == 0:
        return 0.0
    return (statistics.mean(a) - statistics.mean(b)) / se


class CanaryController:
    def __init__(self, margin=0.05, z=2.33, min_samples=30, strikes=2):
        self.margin, self.z, self.min_samples, self.strikes = margin, z, min_samples, strikes
        self.bad_windows = 0

    def observe(self, stable, canary):
        if len(canary) < self.min_samples:
            return "wait"
        diff = statistics.mean(canary) - statistics.mean(stable)
        if diff < -self.margin and welch_t(canary, stable) < -self.z:
            self.bad_windows += 1
            return "rollback" if self.bad_windows >= self.strikes else "watch"
        self.bad_windows = 0
        return "ok"


class CanaryRun:
    def __init__(self, controller=None, promote_after=6):
        self.controller = controller or CanaryController()
        self.promote_after = promote_after
        self.ok_windows = 0
        self.status = "running"
        self.history = []

    def step(self, stable, canary):
        if self.status != "running":
            return self.status
        action = self.controller.observe(stable, canary)
        self.history.append(action)
        if action == "rollback":
            self.status = "rolled_back"
        elif action == "ok":
            self.ok_windows += 1
            if self.ok_windows >= self.promote_after:
                self.status = "promoted"
        return self.status


def validate_card(card):
    issues = []
    for s in REQUIRED_SECTIONS:
        if not card.get(s):
            issues.append(f"missing section: {s}")
    limitations = card.get("limitations", [])
    if len(limitations) < 3:
        issues.append("fewer than 3 limitations")
    for text in limitations:
        if len(text.split()) < 5:
            issues.append(f"vague limitation: {text}")
    for ev in card.get("evaluation", []):
        if not ev.get("dataset"):
            issues.append(f"evaluation without dataset: {ev.get('metric')}")
        if ev.get("label") not in HONEST_LABELS:
            issues.append(f"evaluation without honest label: {ev.get('metric')}")
    for ds in card.get("data_sources", []):
        for key in ("origin", "owner", "license"):
            if not ds.get(key):
                issues.append(f"data source {ds.get('name')} lacks {key}")
    return issues


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def stale_files(card, paths):
    recorded = card.get("config_digest", {})
    return sorted(Path(p).name for p in paths if recorded.get(Path(p).name) != file_digest(p))
