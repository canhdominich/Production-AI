import os
import subprocess
import tempfile
from pathlib import Path

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"

DOCKER_STUB = """#!/usr/bin/env bash
echo "docker $* [APP_TAG=$APP_TAG]" >> "$STUB_LOG"
"""
CURL_STUB = """#!/usr/bin/env bash
[ "$APP_TAG" != "bad" ]
"""


def run_deploy(root, tag):
    bin_dir = root / "bin"
    bin_dir.mkdir(exist_ok=True)
    for name, body in (("docker", DOCKER_STUB), ("curl", CURL_STUB)):
        (bin_dir / name).write_text(body)
        (bin_dir / name).chmod(0o755)
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", APP_TAG=tag, APP_DIR=str(root / "app"),
               HEALTH_RETRIES="3", HEALTH_DELAY="0", STUB_LOG=str(root / "calls.log"))
    (root / "calls.log").write_text("")
    r = subprocess.run(["bash", str(DEPLOY / "deploy.sh")], env=env, capture_output=True, text=True)
    calls = (root / "calls.log").read_text().strip().splitlines()
    return r.returncode, (r.stdout + r.stderr).strip(), calls


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / "app").mkdir()
    print("syntax check:", subprocess.run(["bash", "-n", str(DEPLOY / "deploy.sh")]).returncode == 0)
    for tag in ("v1", "v2", "bad"):
        code, text, calls = run_deploy(root, tag)
        print(f"\ndeploy {tag}: exit {code}")
        print("  message:", text)
        print("  docker calls:", len(calls), "| last:", calls[-1].replace("docker compose -f compose.prod.yaml ", ""))
        print("  .release now:", (root / "app" / ".release").read_text().strip())
