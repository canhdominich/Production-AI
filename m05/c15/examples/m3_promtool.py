import subprocess

import _kit

D = _kit.PROJECT / "deploy"


def promtool(*args):
    r = subprocess.run(["docker", "run", "--rm", "-v", f"{D}:/d:ro", "--entrypoint", "promtool", "prom/prometheus:v3.15.1", *args],
                       capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


print("promtool check rules:")
code, out = promtool("check", "rules", "/d/alerts.yml")
print(" ", out.replace("\n", "\n  "), "| exit", code)
print("promtool test rules (20 percent errors must page, 5 percent must not):")
code, out = promtool("test", "rules", "/d/alerts.test.yml")
print(" ", out.replace("\n", "\n  "), "| exit", code)
