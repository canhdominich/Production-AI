import json
import math
import re
from pathlib import Path

PLATFORM_DIR = Path(__file__).resolve().parent
M05_DIR = PLATFORM_DIR.parent
DATA_DIR = M05_DIR / "data"
LAB_DIR = M05_DIR.parent

FEATURES = ("chat", "knowledge_assistant", "weekly_report_agent")
TIERS = ("small", "medium", "large")
TIER_RANK = {t: i for i, t in enumerate(TIERS)}


def estimate_tokens(text):
    """Cheap token estimate for Vietnamese text: about 3.2 characters per token. Teaching heuristic, not a real tokenizer."""
    if not text:
        return 0
    return max(1, round(len(text) / 3.2))


def messages_text(messages):
    return "\n".join(str(m.get("content", "")) for m in messages)


def estimate_prompt_tokens(messages):
    return sum(estimate_tokens(str(m.get("content", ""))) + 4 for m in messages) + 3


def percentile(values, p):
    xs = sorted(values)
    if not xs:
        raise ValueError("empty list")
    if not 0 <= p <= 100:
        raise ValueError("p must be between 0 and 100")
    k = (len(xs) - 1) * p / 100
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return float(xs[lo])
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def load_json(name):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
