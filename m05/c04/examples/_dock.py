import json
import shutil
import subprocess
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
C04 = HERE.parent
M05 = C04.parent
STACK = C04 / "stack"
TMP = M05.parent.parent.parent / "backup" / "tmp_m05_c04"
API = "http://127.0.0.1:5641"


def sh(*cmd, check=True, cwd=None, env=None):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=env)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}\n{r.stdout[-800:]}\n{r.stderr[-800:]}")
    return r


def compose(*args, file="compose.yaml", check=True, env=None):
    return sh("docker", "compose", "-f", str(STACK / file), *args, check=check, env=env)


def build(tag, dockerfile, context=M05, target=None, args=()):
    cmd = ["docker", "build", "--progress=plain", "-f", str(dockerfile), "-t", tag, *args]
    if target:
        cmd += ["--target", target]
    cmd.append(str(context))
    t0 = time.perf_counter()
    r = sh(*cmd, env={"DOCKER_BUILDKIT": "1", "PATH": "/usr/bin:/usr/local/bin:/bin", "HOME": str(Path.home())})
    log = r.stderr + r.stdout
    return time.perf_counter() - t0, log


def image_info(tag):
    d = json.loads(sh("docker", "image", "inspect", tag).stdout)[0]
    return {"mb": d["Size"] / 1e6, "layers": len(d["RootFS"]["Layers"]), "user": d["Config"].get("User") or "root", "diff_ids": d["RootFS"]["Layers"]}


def cached_steps(log):
    return log.count("CACHED")


def wait_api(timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if httpx.get(f"{API}/ready", timeout=2).status_code == 200:
                return True
        except httpx.TransportError:
            pass
        time.sleep(0.5)
    return False


def ps():
    out = compose("ps", "-a", "--format", "json").stdout.strip()
    rows = json.loads(out) if out.startswith("[") else [json.loads(x) for x in out.splitlines() if x.strip()]
    return {r["Service"]: (r["State"], r.get("Health") or "-", r.get("ExitCode")) for r in rows}


def make_context(dest):
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "c04").mkdir(parents=True)
    shutil.copytree(STACK, dest / "c04" / "stack", ignore=shutil.ignore_patterns("__pycache__", ".venv"))
    shutil.copytree(M05 / "platform", dest / "platform", ignore=shutil.ignore_patterns("__pycache__", "tests"))
    shutil.copytree(M05 / "data", dest / "data")
    return dest
