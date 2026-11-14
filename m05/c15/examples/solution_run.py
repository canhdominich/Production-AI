import re
import subprocess
import sys
from collections import Counter

import _kit


def run(impl):
    env = {"PYTHONPATH": str(_kit.PROJECT / impl), "PATH": "/usr/bin:/bin"}
    out = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider", "tests"], cwd=_kit.PROJECT, env=env,
                         capture_output=True, text=True).stdout
    result = {}
    for line in out.splitlines():
        m = re.match(r"(PASSED|FAILED) \S*/(test_m\d)_\S+::(\S+)", line)
        if m:
            result[m.group(3)] = (m.group(1) == "PASSED", m.group(2))
    return result


LABEL = {"test_m1": "M1 auth and tenants", "test_m2": "M2 release and deploy", "test_m3": "M3 cost and observability", "test_m4": "M4 reliability and canary"}
runs = {impl: run(impl) for impl in ("solution", "starter")}
print(f"{'milestone':28}{'tests':>6}{'solution':>10}{'starter':>9}")
for key, label in LABEL.items():
    names = [n for n, (_, m) in runs["solution"].items() if m == key]
    sol = sum(runs["solution"][n][0] for n in names)
    st = sum(runs["starter"][n][0] for n in names)
    print(f"{label:28}{len(names):>6}{sol:>10}{st:>9}")
total = len(runs["solution"])
print(f"{'total':28}{total:>6}{sum(v[0] for v in runs['solution'].values()):>10}{sum(v[0] for v in runs['starter'].values()):>9}")
