"""Deterministic request generator for the m05 labs (seed 42 by default).

Three features of Giao Hang Anh Ti share one gateway: chat, knowledge_assistant, weekly_report_agent.
Prompts are built from the frozen texts of m02 (customer messages), m03 (questions) and m04 (policy, complaint cases).
Output lengths follow a log-normal distribution, so a few requests are much longer than the median (long tail).
"""
import csv
import json
import math
import random
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache

from common import DATA_DIR, LAB_DIR, estimate_prompt_tokens, load_json

SEED = 42

FEATURE_SPEC = {
    "chat": {"share": 0.70, "tiers": {"small": 0.6, "medium": 0.4}, "out_median": 120, "out_sigma": 0.8, "out_cap": 1500, "stream": True, "steps": 1},
    "knowledge_assistant": {"share": 0.27, "tiers": {"medium": 0.7, "large": 0.3}, "out_median": 240, "out_sigma": 0.6, "out_cap": 1500, "stream": True, "steps": 1},
    "weekly_report_agent": {"share": 0.03, "tiers": {"large": 1.0}, "out_median": 1400, "out_sigma": 0.45, "out_cap": 4000, "stream": False, "steps": 4},
}

SYSTEM = {
    "chat": "Bạn là trợ lý chăm sóc khách hàng của Giao Hàng Anh Tí tại Phố Rôm Rả. Trả lời ngắn gọn, lịch sự, bằng tiếng Việt. Không bịa mã đơn hay số tiền; nếu thiếu thông tin thì hỏi lại khách.",
    "knowledge_assistant": "Bạn là trợ lý tri thức nội bộ của Giao Hàng Anh Tí. Chỉ trả lời dựa trên các đoạn tài liệu được cung cấp, kèm mã đoạn trích dẫn. Nếu tài liệu không đủ, nói rõ là chưa đủ căn cứ.",
    "weekly_report_agent": "Bạn là agent lập báo cáo tuần cho chi nhánh của Giao Hàng Anh Tí. Tổng hợp các khiếu nại trong tuần theo nguyên nhân, nêu số lượng, mức độ nghiêm trọng và đề xuất hành động cho tuần sau.",
}

HOUR_WEIGHTS = [1, 1, 1, 1, 1, 2, 4, 6, 7, 7, 8, 12, 12, 8, 7, 7, 8, 12, 12, 8, 5, 3, 2, 1]
REPORT_HOUR_WEIGHTS = [0, 0, 0, 0, 0, 2, 10, 10, 4, 1] + [0] * 14


@dataclass
class Request:
    request_id: str
    arrival_s: float
    tenant_id: str
    user_id: str
    role: str
    feature: str
    tier: str
    model: str
    stream: bool
    messages: list
    prompt_tokens: int
    output_tokens: int
    max_tokens: int
    steps: int = 1

    def body(self):
        return {"model": self.model, "messages": self.messages, "max_tokens": self.max_tokens, "stream": self.stream}

    def provider_headers(self):
        return {"x-fake-request-id": self.request_id, "x-fake-output-tokens": str(self.output_tokens)}

    def as_dict(self):
        return asdict(self)


@lru_cache(maxsize=1)
def sources():
    with open(LAB_DIR / "m02" / "data" / "messages.csv", encoding="utf-8", newline="") as f:
        messages = [r["text"] for r in csv.DictReader(f)]
    with open(LAB_DIR / "m03" / "data" / "questions.csv", encoding="utf-8", newline="") as f:
        questions = [r["question"] for r in csv.DictReader(f)]
    policy = (LAB_DIR / "m04" / "data" / "policy.md").read_text(encoding="utf-8")
    chunks = [re.sub(r"\*\*", "", p).strip() for p in policy.split("\n\n") if p.startswith("**")]
    with open(LAB_DIR / "m04" / "data" / "cases.csv", encoding="utf-8", newline="") as f:
        cases = [f"{r['case_id']} ({r['case_type']}, {r['channel']}): {r['body']}" for r in csv.DictReader(f)]
    return {"messages": messages, "questions": questions, "chunks": chunks, "cases": cases}


def _weighted(rnd, weights):
    keys = list(weights)
    return rnd.choices(keys, weights=[weights[k] for k in keys])[0]


def _output_tokens(rnd, spec):
    v = math.exp(rnd.gauss(math.log(spec["out_median"]), spec["out_sigma"]))
    return int(max(8, min(spec["out_cap"], round(v))))


def _prompt(rnd, feature, src):
    system = {"role": "system", "content": SYSTEM[feature]}
    if feature == "chat":
        turns = 0
        while turns < 10 and rnd.random() < 0.55:
            turns += 1
        history = []
        for _ in range(turns):
            history.append({"role": "user", "content": rnd.choice(src["messages"])})
            history.append({"role": "assistant", "content": "Dạ, em đã ghi nhận. Anh chị cho em xin mã đơn để em kiểm tra ạ."})
        return [system] + history + [{"role": "user", "content": rnd.choice(src["messages"])}]
    if feature == "knowledge_assistant":
        k = rnd.choice([2, 3, 3, 4, 4, 5, 6, 8])
        ctx = "\n\n".join(rnd.sample(src["chunks"], min(k, len(src["chunks"]))))
        return [system, {"role": "user", "content": f"Tài liệu:\n{ctx}\n\nCâu hỏi: {rnd.choice(src['questions'])}"}]
    n = int(max(12, min(80, round(math.exp(rnd.gauss(math.log(35), 0.4))))))
    cases = "\n".join(rnd.sample(src["cases"], n))
    return [system, {"role": "user", "content": f"Các khiếu nại trong tuần ({n} ca):\n{cases}\n\nHãy lập báo cáo tuần."}]


def _arrival(rnd, weights, duration_s):
    hour = rnd.choices(range(24), weights=weights)[0]
    return (hour + rnd.random()) * duration_s / 24


def generate(n, seed=SEED, duration_s=86400.0, mix=None):
    """Return n requests sorted by arrival time. mix maps feature to share; default is FEATURE_SPEC shares."""
    rnd = random.Random(seed)
    src = sources()
    tenants = load_json("tenants.json")
    prices = load_json("prices.json")
    roles = tenants["roles"]
    shares = mix or {f: s["share"] for f, s in FEATURE_SPEC.items()}
    out = []
    for i in range(n):
        feature = _weighted(rnd, shares)
        spec = FEATURE_SPEC[feature]
        allowed = [t for t in tenants["tenants"] if feature in t["allowed_features"]]
        tenant = rnd.choices(allowed, weights=[t["traffic_share"] for t in allowed])[0]
        users = [u for u in tenant["users"] if feature in roles[u["role"]]["features"]]
        user = rnd.choice(users)
        tier = _weighted(rnd, spec["tiers"])
        messages = _prompt(rnd, feature, src)
        out_tokens = _output_tokens(rnd, spec)
        arrival = _arrival(rnd, REPORT_HOUR_WEIGHTS if feature == "weekly_report_agent" else HOUR_WEIGHTS, duration_s)
        out.append(Request(
            request_id="", arrival_s=round(arrival, 3), tenant_id=tenant["tenant_id"], user_id=user["user_id"], role=user["role"],
            feature=feature, tier=tier, model=prices["tiers"][tier], stream=spec["stream"], messages=messages,
            prompt_tokens=estimate_prompt_tokens(messages), output_tokens=out_tokens,
            max_tokens=min(spec["out_cap"], 4096 if feature == "weekly_report_agent" else 2048), steps=spec["steps"],
        ))
    out.sort(key=lambda r: r.arrival_s)
    for i, r in enumerate(out):
        r.request_id = f"r{seed}-{i:05d}"
    return out


def write_jsonl(requests, path):
    with open(path, "w", encoding="utf-8") as f:
        for r in requests:
            f.write(json.dumps(r.as_dict(), ensure_ascii=False) + "\n")


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [Request(**json.loads(line)) for line in f if line.strip()]
