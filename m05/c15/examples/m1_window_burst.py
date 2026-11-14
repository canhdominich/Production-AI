import subprocess
import time

import redis

import _kit  # noqa: F401
from anhti_platform.limits import RedisWindowLimiter, SlidingWindowLimiter

server = subprocess.Popen(["redis-server", "--port", "5759", "--save", "", "--appendonly", "no"], stdout=subprocess.DEVNULL)
time.sleep(0.6)
try:
    client = redis.Redis(port=5759, protocol=2)
    fixed, sliding = RedisWindowLimiter(client), SlidingWindowLimiter()
    limit, base = 30, 6000.0

    def burst(limiter, key, start, n):
        return sum(limiter.allow(key, limit, start + i * 0.01)[0] for i in range(n))

    ok_fixed = burst(fixed, "br-ben-song", base - 1.0, 40) + burst(fixed, "br-ben-song", base + 0.5, 40)
    ok_slide = burst(sliding, "br-ben-song", base - 1.0, 40) + burst(sliding, "br-ben-song", base + 0.5, 40)
    print("limit per minute:", limit, "| two bursts of 40 requests, 1.5 seconds apart, across a minute boundary")
    print("fixed window in Redis passed:", ok_fixed)
    print("sliding window passed:", ok_slide)
    other = sum(fixed.allow("br-dau-pho", 120, base)[0] for _ in range(30))
    print("another tenant during the same burst, passed:", other, "of 30")
    print("redis server:", client.info()["redis_version"])
finally:
    server.terminate()
