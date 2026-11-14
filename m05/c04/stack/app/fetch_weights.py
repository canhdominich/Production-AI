import hashlib
import os
import sys
import time

import httpx


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url, dest, expected_sha):
    if os.path.exists(dest) and sha256_of(dest) == expected_sha:
        print(f"cache hit: {dest} ({os.path.getsize(dest) / 1e6:.1f} MB), no download")
        return 0
    part = dest + ".part"
    t0 = time.perf_counter()
    with httpx.stream("GET", url, timeout=60) as r, open(part, "wb") as f:
        r.raise_for_status()
        for chunk in r.iter_bytes(1 << 20):
            f.write(chunk)
    got = sha256_of(part)
    if got != expected_sha:
        os.remove(part)
        print(f"checksum mismatch: expected {expected_sha[:12]}, got {got[:12]}; file not installed")
        return 1
    os.replace(part, dest)
    print(f"downloaded {os.path.getsize(dest) / 1e6:.1f} MB in {time.perf_counter() - t0:.2f} s, checksum {got[:12]} verified")
    return 0


if __name__ == "__main__":
    url, dest, sha = sys.argv[1:4]
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    sys.exit(fetch(url, dest, sha))
