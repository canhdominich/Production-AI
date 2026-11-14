import re
import subprocess
import sys
from collections import Counter

import _kit

env = {"PYTHONPATH": str(_kit.PROJECT / "solution"), "PATH": "/usr/bin:/bin"}
out = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider", "tests"], cwd=_kit.PROJECT, env=env,
                     capture_output=True, text=True).stdout
passed, total = Counter(), Counter()
for line in out.splitlines():
    m = re.match(r"(PASSED|FAILED) \S*/(test_m\d)_\S+::(\S+)", line)
    if m:
        total[m.group(2)] += 1
        passed[m.group(2)] += m.group(1) == "PASSED"

docs = _kit.PROJECT / "docs"
rows = []
rows.append(("API functions and security", 20, passed["test_m1"] / total["test_m1"], f"{passed['test_m1']}/{total['test_m1']} tests of milestone 1"))
rows.append(("Deploy and CI/CD with gate", 20, passed["test_m2"] / total["test_m2"], f"{passed['test_m2']}/{total['test_m2']} tests of milestone 2"))
rows.append(("Observability and cost", 25, passed["test_m3"] / total["test_m3"], f"{passed['test_m3']}/{total['test_m3']} tests of milestone 3"))
rows.append(("Reliability (SLO, fallback, chaos)", 20, passed["test_m4"] / total["test_m4"], f"{passed['test_m4']}/{total['test_m4']} tests of milestone 4"))
perf_ok = (docs / "loadtest_report.md").exists() and "429" in (docs / "loadtest_report.md").read_text()
rows.append(("Performance (load test with numbers)", 10, 1.0 if perf_ok else 0.0, "docs/loadtest_report.md with a table" if perf_ok else "no load test report"))
doc_ok = all((docs / f).exists() for f in ("runbook.md", "system_card.md"))
rows.append(("Operations docs", 5, 1.0 if doc_ok else 0.0, "runbook.md and system_card.md present" if doc_ok else "missing"))
print(f"{'criterion':38}{'weight':>7}{'earned':>8}  evidence")
for name, w, share, ev in rows:
    print(f"{name:38}{w:>7}{w * share:>8.1f}  {ev}")
print(f"{'total':38}{sum(r[1] for r in rows):>7}{sum(r[1] * r[2] for r in rows):>8.1f}")
