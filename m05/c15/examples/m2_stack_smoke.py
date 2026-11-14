import json
import os
import subprocess
import time

import httpx

import _kit

env = dict(os.environ, **_kit.STACK_ENV)
compose = ["docker", "compose", "-f", str(_kit.PROJECT / "deploy" / "compose.yaml")]
build = subprocess.run(["docker", "build", "-q", "-f", str(_kit.PROJECT / "deploy" / "Dockerfile"), "-t", "m05c15-platform:1", str(_kit.LAB)],
                       capture_output=True, text=True)
subprocess.run(compose + ["up", "-d", "--wait", "--force-recreate"], env=env, capture_output=True, text=True, check=True)
ps = json.loads(subprocess.run(compose + ["ps", "--format", "json"], env=env, capture_output=True, text=True).stdout)
for s in sorted(ps, key=lambda x: x["Service"]):
    print(f"{s['Service']:20} {s['State']:8} {s.get('Health') or '-'}")

https = httpx.Client(base_url="https://localhost:5758", verify=False, timeout=20)
login = https.post("/auth/token", json={"user_id": "dp-03", "password": env["DEMO_PASSWORD"]})
auth = {"authorization": "Bearer " + login.json()["access_token"]}
print("\nlogin over HTTPS:", login.status_code)
chat = https.post("/v1/chat", json={"message": "don at047838 bao gio toi"}, headers=auth)
print("chat over HTTPS:", chat.status_code, "| provider", chat.json()["provider"], "| model", chat.json()["model"])
print("http to https redirect:", httpx.get("http://localhost:5757/", follow_redirects=False).status_code)
print("/metrics through Caddy:", https.get("/metrics").status_code, "| directly on the internal port:", httpx.get(_kit.API + "/metrics").status_code)
print("no token:", https.get("/v1/usage").status_code)
big = https.post("/v1/chat", content=b"x" * 70000, headers={**auth, "content-type": "application/json"})
print("70 KB body through Caddy:", big.status_code)
usage = https.get("/v1/usage", headers=auth).json()
print("usage for br-dau-pho has requests:", usage["requests"] >= 1)
time.sleep(6)
targets = httpx.get(_kit.PROM + "/api/v1/targets").json()["data"]["activeTargets"]
print("prometheus targets:", [(t["labels"]["job"], t["health"]) for t in targets])
print("\nimage size (MB):", round(int(subprocess.run(["docker", "image", "inspect", "m05c15-platform:1", "--format", "{{.Size}}"],
                                                       capture_output=True, text=True).stdout) / 1e6))
