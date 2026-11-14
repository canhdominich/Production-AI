import datetime
import re
from urllib.parse import quote

import httpx
from packaging.version import Version

INDEX = "https://download.pytorch.org/whl"
http = httpx.Client(timeout=30, follow_redirects=True)
print("checked on", datetime.date.today().isoformat(), "(download sizes from the index, nothing downloaded)")


def latest(flavour):
    html = http.get(f"{INDEX}/{flavour}/torch/").text
    names = set(re.findall(r'>(torch-[^<]*cp312-cp312-manylinux_2_28_x86_64\.whl)<', html))
    return max(names, key=lambda n: Version(n.split("-")[1].split("+")[0])), html


def size(url):
    return int(http.head(url).headers["content-length"])


cpu_name, _ = latest("cpu")
version = cpu_name.split("-")[1].split("+")[0]
flavour = next(c for c in ("cu134", "cu132", "cu130", "cu129", "cu128") if cpu_name.replace("+cpu", f"+{c}") in http.get(f"{INDEX}/{c}/torch/").text)
cuda_name = cpu_name.replace("+cpu", f"+{flavour}")
cpu_mb = size(f"{INDEX}/cpu/{quote(cpu_name)}") / 1e6
cuda_mb = size(f"{INDEX}/{flavour}/{quote(cuda_name)}") / 1e6

meta = http.get(f"{INDEX}/{flavour}/{quote(cuda_name)}.metadata").text
deps = re.findall(r"^Requires-Dist: ((?:nvidia-[\w-]+|triton))==([\w.]+);", meta, flags=re.M)
extra = 0
for name, ver in deps:
    files = http.get(f"https://pypi.org/pypi/{name}/{ver}/json").json()["urls"]
    wheel = next(f for f in files if "manylinux" in f["filename"] and "x86_64" in f["filename"])
    extra += wheel["size"]

print(f"torch {version} CPU wheel:              {cpu_mb:8.0f} MB")
print(f"torch {version} {flavour} wheel:           {cuda_mb:8.0f} MB")
print(f"nvidia-* and triton wheels it needs ({len(deps)}): {extra / 1e6:6.0f} MB")
print(f"CUDA total download: {(cuda_mb + extra / 1e6):.0f} MB, {(cuda_mb + extra / 1e6) / cpu_mb:.1f} times the CPU wheel")

for repo, tag in (("library/python", "3.12-slim"), ("library/python", "3.12"), ("nvidia/cuda", "12.8.1-runtime-ubuntu24.04"), ("nvidia/cuda", "12.8.1-cudnn-runtime-ubuntu24.04")):
    d = http.get(f"https://hub.docker.com/v2/repositories/{repo}/tags/{tag}").json()
    amd = next(i["size"] for i in d["images"] if i["architecture"] == "amd64")
    print(f"Docker Hub {repo}:{tag}".ljust(60), f"{amd / 1e6:7.0f} MB")
