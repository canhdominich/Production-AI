import sys
import urllib.request

import redis

from app import settings

target = sys.argv[1]
try:
    if target == "worker":
        if not redis.Redis.from_url(settings.REDIS_URL).exists(settings.HEARTBEAT):
            sys.exit("no heartbeat")
    else:
        with urllib.request.urlopen(target, timeout=2) as r:
            if r.status != 200:
                sys.exit(f"status {r.status}")
except Exception as e:
    sys.exit(f"unhealthy: {e}")
