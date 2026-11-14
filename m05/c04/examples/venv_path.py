from _dock import STACK, build, sh

build("m05c04-badpath:1", STACK / "variants" / "Dockerfile.badpath")
r = sh("docker", "run", "--rm", "m05c04-badpath:1", check=False)
print("exit code:", r.returncode)
print("stderr:", r.stderr.strip().splitlines()[-1][:160])
r = sh("docker", "run", "--rm", "--entrypoint", "head", "m05c04-badpath:1", "-1", "/opt/venv/bin/uvicorn")
print("first line of /opt/venv/bin/uvicorn:", r.stdout.strip())
r = sh("docker", "run", "--rm", "--entrypoint", "ls", "m05c04-badpath:1", "/app/.venv/bin", check=False)
print("ls /app/.venv/bin:", r.stderr.strip().splitlines()[-1][:100])
