from pathlib import Path

from _workflow import check, load

DEPLOY = Path(__file__).resolve().parents[1] / "deploy" / "workflows"

for name in ("ci_bad.yml", "ci.yml"):
    doc = load(DEPLOY / name)
    problems = check(doc)
    print(f"{name}: {len(doc['jobs'])} jobs, {len(problems)} problems")
    for p in problems:
        print("  -", p)
