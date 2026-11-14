import json
import random
import shutil
import tarfile
import time

from _dock import STACK, TMP, build, image_info, sh

CTX = TMP / "ctx_weights"
MB = 200
shutil.rmtree(CTX, ignore_errors=True)
(CTX / "app").mkdir(parents=True)
(CTX / "weights").mkdir()
for name in ("Dockerfile.weights_first", "Dockerfile.weights_last", "Dockerfile.slim_code"):
    shutil.copy(STACK / "variants" / name, CTX / name)


def write_weights(seed):
    rnd = random.Random(seed)
    with open(CTX / "weights" / "model.bin", "wb") as f:
        for _ in range(MB):
            f.write(rnd.randbytes(1_000_000))


def write_app(version):
    (CTX / "app" / "serve.py").write_text(f"VERSION = {version}\nprint('serving model with app version', VERSION)\n")


def layer_sizes(tag):
    tar_path = TMP / "image.tar"
    sh("docker", "save", "-o", str(tar_path), tag)
    with tarfile.open(tar_path) as tf:
        manifest = json.loads(tf.extractfile("manifest.json").read())[0]
        sizes = [tf.getmember(p).size for p in manifest["Layers"]]
    tar_path.unlink()
    return dict(zip(image_info(tag)["diff_ids"], sizes))


def pull_mb(old, new):
    old_layers, new_layers = layer_sizes(old), layer_sizes(new)
    return sum(s for d, s in new_layers.items() if d not in old_layers) / 1e6


rows = []
for label, dockerfile, tag in (("weights baked, copied first", "Dockerfile.weights_first", "first"), ("weights baked, copied last", "Dockerfile.weights_last", "last"), ("weights outside the image", "Dockerfile.slim_code", "slim")):
    write_weights(1)
    write_app(1)
    build(f"m05c04-w-{tag}:1", CTX / dockerfile, context=CTX)
    write_app(2)
    t0 = time.perf_counter()
    build(f"m05c04-w-{tag}:2", CTX / dockerfile, context=CTX)
    rebuild_s = time.perf_counter() - t0
    code_pull = pull_mb(f"m05c04-w-{tag}:1", f"m05c04-w-{tag}:2")
    write_weights(2)
    build(f"m05c04-w-{tag}:3", CTX / dockerfile, context=CTX)
    model_pull = pull_mb(f"m05c04-w-{tag}:2", f"m05c04-w-{tag}:3")
    rows.append((label, image_info(f"m05c04-w-{tag}:1")["mb"], rebuild_s, code_pull, model_pull))

print(f"synthetic weights file: {MB} MB of random bytes (stands for a small model)")
print(f"{'strategy':<30}{'image MB':>9}{'rebuild s':>10}{'pull: code edit':>17}{'pull: new model':>17}")
for label, size, secs, code_pull, model_pull in rows:
    print(f"{label:<30}{size:>9.0f}{secs:>10.1f}{code_pull:>15.1f} MB{model_pull:>15.1f} MB")
for t in ("first", "last", "slim"):
    for v in (1, 2, 3):
        sh("docker", "rmi", f"m05c04-w-{t}:{v}", check=False)
shutil.rmtree(CTX, ignore_errors=True)
