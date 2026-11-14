import ssl
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
DEPLOY = HERE.parent / "deploy"
NAME = "m05c05-caddy"
HTTPS = "https://localhost:5651"


def start_caddy(caddyfile):
    subprocess.run(["docker", "rm", "-f", NAME], capture_output=True)
    subprocess.run(["docker", "run", "-d", "--rm", "--name", NAME, "--network", "host",
                    "-v", f"{DEPLOY / caddyfile}:/etc/caddy/Caddyfile:ro", "caddy:2-alpine"],
                   check=True, capture_output=True)
    for _ in range(60):
        try:
            httpx.get(HTTPS + "/health", verify=False, timeout=1)
            return
        except httpx.HTTPError:
            time.sleep(0.5)
    raise SystemExit("caddy did not start")


def fetch_root():
    root = Path(tempfile.mkdtemp()) / "root.crt"
    subprocess.run(["docker", "cp", f"{NAME}:/data/caddy/pki/authorities/local/root.crt", str(root)], check=True, capture_output=True)
    return root


def abandoned_stream(client):
    with client.stream("GET", HTTPS + "/long") as r:
        for i, line in enumerate(r.iter_lines()):
            if i == 2:
                break
    time.sleep(3)
    return client.get(HTTPS + "/stats").json()["n"]


def stream_times(client):
    t0 = time.perf_counter()
    stamps = []
    with client.stream("GET", HTTPS + "/stream") as r:
        for line in r.iter_lines():
            if line:
                stamps.append(time.perf_counter() - t0)
    return stamps


app = subprocess.Popen([sys.executable, "-m", "uvicorn", "_demo_app:app", "--port", "5650", "--log-level", "warning"], cwd=HERE)
try:
    start_caddy("Caddyfile.local")
    root = fetch_root()

    r = httpx.get("http://localhost:5652/health", follow_redirects=False)
    print(f"HTTP request: status {r.status_code}, redirected to {r.headers['location'].split(':')[0]}")

    try:
        httpx.get(HTTPS + "/health")
    except httpx.ConnectError as e:
        print("default trust store:", str(e).split("(")[0].strip())

    with httpx.Client(verify=ssl.create_default_context(cafile=str(root))) as c:
        r = c.get(HTTPS + "/health")
        tls = r.extensions["network_stream"].get_extra_info("ssl_object")
        print(f"HTTPS with Caddy root certificate: status {r.status_code}, {tls.version()}, issuer {dict(x[0] for x in tls.getpeercert()['issuer'])['commonName']}")
        print("body 100 KB:", c.post(HTTPS + "/echo", content=b"x" * 100_000).status_code)
        print("body 2 MB:", c.post(HTTPS + "/echo", content=b"x" * 2_000_000).status_code)
        s = stream_times(c)
        print("chunk arrival in seconds:", [round(x, 2) for x in s])
        print("user closes the tab after 3 tokens, tokens the backend produced:", abandoned_stream(c))

finally:
    subprocess.run(["docker", "rm", "-f", NAME], capture_output=True)
    app.terminate()
