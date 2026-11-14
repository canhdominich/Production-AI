import argparse
import hashlib
import json
import sys
import tomllib
from collections import defaultdict
from pathlib import Path


def load_cases(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def scripted_model(version, rates):
    def answer(case):
        h = int(hashlib.sha256(case["id"].encode()).hexdigest()[:8], 16) / 2**32
        return case["expected"] if h < rates[version][case["category"]] else "other"
    return answer


def run_cases(cases, answer_fn):
    return [{"id": c["id"], "category": c["category"], "ok": answer_fn(c) == c["expected"]} for c in cases]


def pass_rate(results):
    return sum(r["ok"] for r in results) / len(results) if results else 0.0


def by_category(results):
    groups = defaultdict(list)
    for r in results:
        groups[r["category"]].append(r["ok"])
    return {k: sum(v) / len(v) for k, v in sorted(groups.items())}


def decide(baseline, candidate, max_drop=0.05, max_category_drop=0.17, min_cases=60, min_pass=0.80):
    reasons = []
    if len(candidate) < min_cases:
        reasons.append(f"only {len(candidate)} cases, need {min_cases}")
    b, c = pass_rate(baseline), pass_rate(candidate)
    if c < min_pass:
        reasons.append(f"pass rate {c:.3f} below floor {min_pass}")
    if b - c > max_drop:
        reasons.append(f"overall drop {b - c:.3f} above {max_drop}")
    bc, cc = by_category(baseline), by_category(candidate)
    for cat, rate in cc.items():
        if bc.get(cat, rate) - rate > max_category_drop:
            reasons.append(f"category {cat} dropped {bc[cat] - rate:.3f}")
    return {"decision": "block" if reasons else "deploy", "baseline": round(b, 3), "candidate": round(c, 3),
            "by_category": {k: round(v, 3) for k, v in cc.items()}, "reasons": reasons}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True)
    ap.add_argument("--rates", required=True)
    ap.add_argument("--thresholds", required=True)
    ap.add_argument("--baseline", default="v1")
    ap.add_argument("--candidate", required=True)
    a = ap.parse_args(argv)
    cases = load_cases(a.cases)
    rates = json.loads(Path(a.rates).read_text())
    thresholds = tomllib.loads(Path(a.thresholds).read_text())["gate"]
    report = decide(run_cases(cases, scripted_model(a.baseline, rates)), run_cases(cases, scripted_model(a.candidate, rates)), **thresholds)
    print(json.dumps(report, indent=2))
    return 0 if report["decision"] == "deploy" else 1


if __name__ == "__main__":
    sys.exit(main())
