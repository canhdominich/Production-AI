import yaml


def load(path):
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    if True in doc and "on" not in doc:
        doc["on"] = doc.pop(True)
    return doc


def needs_of(job):
    n = job.get("needs", [])
    return [n] if isinstance(n, str) else list(n)


def ancestors(jobs, name, seen=None):
    seen = set() if seen is None else seen
    for dep in needs_of(jobs[name]):
        if dep not in seen:
            seen.add(dep)
            ancestors(jobs, dep, seen)
    return seen


def check(doc):
    problems = []
    jobs = doc.get("jobs", {})
    for req in ("test", "eval-gate", "deploy"):
        if req not in jobs:
            problems.append(f"missing job {req}")
    if problems:
        return problems
    if "eval-gate" not in ancestors(jobs, "deploy"):
        problems.append("deploy does not depend on eval-gate")
    if "test" not in ancestors(jobs, "deploy"):
        problems.append("deploy does not depend on test")
    gate_steps = jobs["eval-gate"].get("steps", [])
    if any(s.get("continue-on-error") for s in gate_steps):
        problems.append("eval-gate uses continue-on-error, a failing gate would not stop deploy")
    cond = str(jobs["deploy"].get("if", ""))
    if "refs/heads/main" not in cond:
        problems.append("deploy is not limited to the main branch")
    for name, job in jobs.items():
        for step in job.get("steps", []):
            ref = step.get("uses", "")
            if ref and "@" in ref and ref.split("@")[1] in ("main", "master", "latest"):
                problems.append(f"{name}: action {ref} is not pinned to a version")
            run = step.get("run", "")
            if "secrets." in run:
                problems.append(f"{name}: secret expanded inside run, pass it through env")
        if "timeout-minutes" not in job:
            problems.append(f"{name}: no timeout-minutes")
    if "permissions" not in doc:
        problems.append("no top-level permissions block")
    return problems
