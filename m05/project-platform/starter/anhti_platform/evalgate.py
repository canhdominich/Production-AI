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
    # TODO 5: chặn khi ít ca, dưới ngưỡng sàn, tụt tổng thể quá max_drop hoặc một nhóm tụt quá max_category_drop; trả dict gồm decision, reasons
    return {"decision": "deploy", "baseline": 0.0, "candidate": 0.0, "by_category": {}, "reasons": []}


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
