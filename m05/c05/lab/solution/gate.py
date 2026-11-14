import json
import sys


def pass_rate(results):
    # Tỉ lệ ca đạt trên toàn bộ bộ đánh giá
    return sum(1 for r in results if r["passed"]) / len(results)


def by_category(results):
    groups = {}
    for r in results:
        groups.setdefault(r["category"], []).append(r["passed"])
    return {name: sum(1 for p in flags if p) / len(flags) for name, flags in groups.items()}


def decide(baseline, candidate, max_drop=0.05, max_category_drop=0.17, min_cases=20):
    reasons = []
    if len(candidate) < min_cases:
        reasons.append(f"too_few_cases: {len(candidate)} < {min_cases}")
    drop = pass_rate(baseline) - pass_rate(candidate)
    if drop > max_drop + 1e-9:
        reasons.append(f"overall_drop: {drop:.3f} > {max_drop}")
    base_cat, cand_cat = by_category(baseline), by_category(candidate)
    for name in sorted(base_cat):
        cat_drop = base_cat[name] - cand_cat.get(name, 0.0)
        if cat_drop > max_category_drop + 1e-9:
            reasons.append(f"category_drop:{name}: {cat_drop:.3f} > {max_category_drop}")
    return {"ok": not reasons, "reasons": reasons}


def check_workflow(doc):
    problems = []
    jobs = doc.get("jobs", {})
    deploy, gate = jobs.get("deploy"), jobs.get("eval-gate")
    if deploy is None or gate is None:
        return ["missing_job"]
    needs = deploy.get("needs", [])
    needs = [needs] if isinstance(needs, str) else needs
    if "eval-gate" not in needs:
        problems.append("deploy_not_after_gate")
    if any(step.get("continue-on-error") for step in gate.get("steps", [])):
        problems.append("gate_continue_on_error")
    if "refs/heads/main" not in str(deploy.get("if", "")):
        problems.append("deploy_not_main_only")
    for job in jobs.values():
        if any("secrets." in step.get("run", "") for step in job.get("steps", [])):
            problems.append("secret_in_run")
            break
    return problems


def main(argv):
    baseline = json.load(open(argv[0], encoding="utf-8"))
    candidate = json.load(open(argv[1], encoding="utf-8"))
    result = decide(baseline, candidate)
    print("gate:", "PASS" if result["ok"] else "BLOCK")
    for reason in result["reasons"]:
        print(" -", reason)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
