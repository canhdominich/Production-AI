import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
STATEFUL = ("postgres", "redis")


def audit(doc):
    found = []
    for name, svc in doc["services"].items():
        image = svc.get("image", "")
        tag = image.rsplit(":", 1)[1] if ":" in image.split("/")[-1] else ""
        if tag in ("", "latest"):
            found.append(f"{name}: image '{image}' has no fixed tag")
        if "restart" not in svc:
            found.append(f"{name}: no restart policy")
        for port in svc.get("ports", []):
            host_ip = str(port).split(":")[0] if str(port).count(":") == 2 else "0.0.0.0"
            if name in STATEFUL and host_ip == "0.0.0.0":
                found.append(f"{name}: port {port} is open to the whole internet")
        env = svc.get("environment", {})
        for key, value in (env.items() if isinstance(env, dict) else []):
            literal = "${" not in str(value)
            has_secret = ("PASSWORD" in key and not key.endswith("_FILE")) or re.search(r"://[^:/@]+:[^@$]+@", str(value))
            if has_secret and literal:
                found.append(f"{name}: {key} contains a password written in the file")
        if name in STATEFUL and "healthcheck" not in svc:
            found.append(f"{name}: no healthcheck")
    return found


def compose_config_ok(path):
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(path, Path(tmp) / "compose.yaml")
        shutil.copy(DEPLOY / "Caddyfile", tmp)
        (Path(tmp) / ".env").write_text("APP_ENV=prod\n")
        (Path(tmp) / "secrets").mkdir()
        (Path(tmp) / "secrets" / "pg_password.txt").write_text("x\n")
        env = dict(os.environ, APP_TAG="1.0.0", SITE_ADDRESS="api.example.com")
        r = subprocess.run(["docker", "compose", "-f", "compose.yaml", "config", "-q"], cwd=tmp, env=env, capture_output=True, text=True)
        return r.returncode == 0, r.stderr.strip()


for name in ("compose.naive.yaml", "compose.prod.yaml"):
    doc = yaml.safe_load((DEPLOY / name).read_text())
    found = audit(doc)
    ok, err = compose_config_ok(DEPLOY / name)
    print(f"{name}: {len(doc['services'])} services, {len(found)} findings, docker compose config {'ok' if ok else 'error'}")
    for f in found:
        print("  -", f)
