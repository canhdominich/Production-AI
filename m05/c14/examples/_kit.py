import hashlib
import importlib.util
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
PLATFORM = str(BASE / "platform")
DATA = HERE.parent / "data"
STACK = HERE.parent / "stack"
MESSAGES = BASE.parent / "m02" / "data" / "messages.csv"
if PLATFORM not in sys.path:
    sys.path.insert(0, PLATFORM)

from workload import generate


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_llm = _load("lab_llm", BASE.parent / "common" / "llm.py")
FakeLLM, LLM = _llm.FakeLLM, _llm.LLM

FEATURES = ("chat", "knowledge_assistant", "weekly_report_agent")
TRUE_PASS = {"chat": 0.90, "knowledge_assistant": 0.80, "weekly_report_agent": 0.70}
JUDGE_TPR, JUDGE_TNR = 0.92, 0.80
THUMBS_DOWN_IF_BAD, THUMBS_DOWN_IF_GOOD = 0.15, 0.01


def unit_hash(request_id, salt="eval-v1"):
    digest = hashlib.sha256(f"{salt}:{request_id}".encode()).hexdigest()
    return int(digest[:8], 16) / 2**32


def day_log(day, n=2000, pass_override=None):
    """One simulated production day: real request mix from the shared workload, hidden quality label per request."""
    rnd = random.Random(9000 + day)
    rows = []
    for r in generate(n, seed=100 + day):
        p = (pass_override or {}).get(r.feature, TRUE_PASS[r.feature])
        good = rnd.random() < p
        thumbs = rnd.random() < (THUMBS_DOWN_IF_GOOD if good else THUMBS_DOWN_IF_BAD)
        rows.append({"id": r.request_id, "feature": r.feature, "tenant": r.tenant_id, "good": good, "thumbs_down": thumbs})
    return rows


def wilson(passes, n, z=1.96):
    if n == 0:
        return 0.0, 1.0
    p = passes / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)


def psi(expected, actual, eps=1e-4):
    """Population stability index between two lists of counts over the same categories."""
    e_total, a_total = sum(expected), sum(actual)
    score = 0.0
    for e, a in zip(expected, actual):
        pe, pa = max(e / e_total, eps), max(a / a_total, eps)
        score += (pa - pe) * math.log(pa / pe)
    return score
