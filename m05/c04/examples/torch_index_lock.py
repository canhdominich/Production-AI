import re
import shutil
import subprocess

from _dock import TMP

PROJECT = TMP / "lock_torch"
shutil.rmtree(PROJECT, ignore_errors=True)
PROJECT.mkdir(parents=True)
HEADER = '[project]\nname = "demo"\nversion = "0.1.0"\nrequires-python = ">=3.12"\ndependencies = ["torch"]\n'
CPU = '\n[[tool.uv.index]]\nname = "pytorch-cpu"\nurl = "https://download.pytorch.org/whl/cpu"\nexplicit = true\n\n[tool.uv.sources]\ntorch = { index = "pytorch-cpu" }\n'

for label, extra in (("default PyPI index", ""), ("pytorch-cpu index", CPU)):
    (PROJECT / "pyproject.toml").write_text(HEADER + extra)
    (PROJECT / "uv.lock").unlink(missing_ok=True)
    subprocess.run(["uv", "lock", "-q"], cwd=PROJECT, check=True, capture_output=True)
    lock = (PROJECT / "uv.lock").read_text()
    pkg = re.search(r'name = "torch"\nversion = "([^"]+)"', lock).group(1)
    nvidia = len(set(re.findall(r'name = "(nvidia-[\w-]+)"', lock)))
    source = re.search(r'name = "torch"\nversion = "[^"]+"\nsource = \{ registry = "([^"]+)"', lock).group(1)
    print(f"{label:<20} torch {pkg:<12} source {source}  nvidia-* packages in lock: {nvidia}")
shutil.rmtree(PROJECT, ignore_errors=True)
