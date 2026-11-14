import hashlib
import os
import random
import shutil

from _dock import TMP, compose

HUB = TMP / "hub"
shutil.rmtree(HUB, ignore_errors=True)
HUB.mkdir(parents=True)
rnd = random.Random(1)
h = hashlib.sha256()
with open(HUB / "model.bin", "wb") as f:
    for _ in range(150):
        chunk = rnd.randbytes(1_000_000)
        h.update(chunk)
        f.write(chunk)
SHA = h.hexdigest()
F = "variants/compose.weights.yaml"
env = dict(os.environ, HUB_DIR=str(HUB), MODEL_SHA256=SHA)


def run(*args, e=env):
    r = compose(*args, file=F, check=False, env=e)
    return r.returncode, (r.stdout + r.stderr).strip().splitlines()


def last(lines, key):
    return next(x for x in reversed(lines) if key in x).strip()


compose("down", "-v", "--remove-orphans", file=F, env=env)
compose("up", "-d", "--wait", "hub", file=F, env=env)
print("1. first start:         ", last(run("run", "--rm", "model-init")[1], "downloaded"))
print("2. second start:        ", last(run("run", "--rm", "model-init")[1], "cache hit"))
run("run", "--rm", "--entrypoint", "sh", "model-init", "-c", "truncate -s 1000000 /models/model.bin")
print("3. after truncating it: ", last(run("run", "--rm", "model-init")[1], "downloaded"))
code, lines = run("run", "--rm", "model-user")
print("4. consumer container:  ", last(lines, "model-user sees"))
bad = dict(env, MODEL_SHA256="0" * 64)
code, lines = run("run", "--rm", "model-init", e=bad)
print(f"5. wrong checksum:       exit {code}, {last(lines, 'checksum mismatch')}")
code, lines = run("run", "--rm", "--no-deps", "--entrypoint", "sh", "model-init", "-c", "ls -l /models/model.bin | awk '{print $5}'")
print("   file kept in volume:  ", next(x for x in reversed(lines) if x.strip().isdigit()).strip(), "bytes, still the verified file")
code, lines = run("run", "--rm", "-v", "scratch:/scratch", "model-init", "python", "-m", "app.fetch_weights", "http://hub:8080/model.bin", "/scratch/model.bin", SHA)
print(f"6. fresh root volume:    exit {code}, {lines[-1][:90]}")
compose("down", "-v", "--remove-orphans", file=F, env=env)
shutil.rmtree(HUB, ignore_errors=True)
