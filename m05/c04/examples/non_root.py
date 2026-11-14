from _dock import sh

for tag in ("m05c04-naive:1", "m05c04-app:1"):
    who = sh("docker", "run", "--rm", tag, "id", "-un").stdout.strip()
    w = sh("docker", "run", "--rm", tag, "sh", "-c", "touch /app/app/injected.py && echo wrote-code-file", check=False)
    msg = (w.stdout + w.stderr).strip().splitlines()[-1]
    print(f"{tag:<16} user={who:<5} write into /app: {msg}")
ro = sh("docker", "run", "--rm", "--read-only", "m05c04-app:1", "sh", "-c", "touch /tmp/x", check=False)
print("read-only rootfs, write /tmp/x:", (ro.stdout + ro.stderr).strip().splitlines()[-1])
ro = sh("docker", "run", "--rm", "--read-only", "--tmpfs", "/tmp", "m05c04-app:1", "sh", "-c", "touch /tmp/x && echo tmpfs-ok", check=False)
print("read-only plus tmpfs /tmp:", (ro.stdout + ro.stderr).strip().splitlines()[-1])
