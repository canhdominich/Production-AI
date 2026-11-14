import subprocess

import _kit

r = subprocess.run(["docker", "compose", "-f", str(_kit.PROJECT / "deploy" / "compose.yaml"), "config", "-q"], capture_output=True, text=True,
                   env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": "/tmp", "JWT_SECRET": "x" * 40, "KEY_PEPPER": "p", "DEMO_PASSWORD": "d"})
print("exit code:", r.returncode)
print(r.stderr.strip().splitlines()[-1])
raise SystemExit(r.returncode)
