import re
import subprocess
import sys
from collections import Counter

import _kit

env = {"PYTHONPATH": str(_kit.PROJECT / "solution"), "PATH": "/usr/bin:/bin"}
out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "tests"], cwd=_kit.PROJECT, env=env,
                     capture_output=True, text=True).stdout
count = Counter(re.search(r"/(test_m\d)_", line).group(1) for line in out.splitlines() if "::" in line)
names = {"test_m1": "Milestone 1: auth, tenants, rate limit", "test_m2": "Milestone 2: release gate, CI, compose",
         "test_m3": "Milestone 3: cost, metrics, traces, logs", "test_m4": "Milestone 4: fallback, breaker, canary"}
for k in sorted(count):
    print(f"{count[k]:3d} tests  {names[k]}")
print(f"{sum(count.values()):3d} tests  total")
