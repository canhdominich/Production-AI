import os
import tempfile
import time
from pathlib import Path

SIZE_MIB = 512
CHUNK = os.urandom(1024 * 1024)


def read_all(path):
    t0 = time.perf_counter()
    with open(path, "rb", buffering=0) as f:
        while f.read(8 * 1024 * 1024):
            pass
    return time.perf_counter() - t0


def drop_cache(path):
    fd = os.open(path, os.O_RDONLY)
    os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
    os.close(fd)


with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
    path = Path(d) / "weights.bin"
    with open(path, "wb") as f:
        for _ in range(SIZE_MIB):
            f.write(CHUNK)
        f.flush()
        os.fsync(f.fileno())
    drop_cache(path)
    cold = read_all(path)
    warm = read_all(path)

gib = SIZE_MIB / 1024
print(f"file {SIZE_MIB} MiB")
print(f"first read, cache dropped: {cold:.2f} s, {gib / cold:.2f} GiB/s")
print(f"second read, in page cache: {warm:.2f} s, {gib / warm:.2f} GiB/s")
print(f"ratio: {cold / warm:.1f}x")
