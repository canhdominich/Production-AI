import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "eval_cases.json"


def load_suite():
    return json.loads(DATA.read_text(encoding="utf-8"))


def answer(suite, version, case):
    missing = suite["versions"][version]["missing"]
    if case["id"] in missing:
        return "Mình sẽ chuyển câu hỏi này cho nhân viên hỗ trợ."
    return suite["facts"][case["id"]]


def run_eval(suite, version):
    results = []
    for case in suite["cases"]:
        text = answer(suite, version, case)
        results.append({"id": case["id"], "category": case["category"], "passed": case["must_contain"] in text})
    return results


def pass_rate(results):
    return sum(r["passed"] for r in results) / len(results)


def by_category(results):
    groups = {}
    for r in results:
        groups.setdefault(r["category"], []).append(r["passed"])
    return {c: sum(v) / len(v) for c, v in groups.items()}


def decide(base, cand, max_drop=0.05, max_category_drop=0.17, min_cases=20):
    reasons = []
    if len(cand) < min_cases:
        reasons.append(f"only {len(cand)} cases, need at least {min_cases}")
    drop = pass_rate(base) - pass_rate(cand)
    if drop > max_drop + 1e-9:
        reasons.append(f"overall drop {drop:.3f} is above {max_drop}")
    bc, cc = by_category(base), by_category(cand)
    for cat in sorted(bc):
        d = bc[cat] - cc.get(cat, 0.0)
        if d > max_category_drop + 1e-9:
            reasons.append(f"category {cat} dropped {d:.3f} (limit {max_category_drop})")
    return {"ok": not reasons, "reasons": reasons}
