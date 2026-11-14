import redis
from _sec import PORT_REDIS, redis_server

LIMIT = 60
WINDOW = 60

SLIDING = """
local key, now, window, limit = KEYS[1], tonumber(ARGV[1]), tonumber(ARGV[2]), tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
if redis.call('ZCARD', key) < limit then
  redis.call('ZADD', key, now, ARGV[4])
  redis.call('EXPIRE', key, math.ceil(window))
  return 1
end
return 0
"""


def fixed_allow(r, tenant, now):
    key = f"rl:fixed:{tenant}:{int(now // WINDOW)}"
    n = r.incr(key)
    if n == 1:
        r.expire(key, WINDOW * 2)
    return n <= LIMIT


with redis_server() as port:
    r = redis.Redis(port=port, decode_responses=True, protocol=2)
    sliding = r.register_script(SLIDING)
    burst = [59.9] * LIMIT + [60.1] * LIMIT
    ok_fixed = sum(fixed_allow(r, "br-ben-song", t) for t in burst)
    print(f"fixed window  : {ok_fixed} of {len(burst)} requests allowed in 0.2 seconds (limit {LIMIT} per minute)")
    ok_slide = 0
    for i, t in enumerate(burst):
        ok_slide += sliding(keys=["rl:slide:br-ben-song"], args=[t, WINDOW, LIMIT, f"{t}-{i}"])
    print(f"sliding window: {ok_slide} of {len(burst)} requests allowed in 0.2 seconds")
    later = sliding(keys=["rl:slide:br-ben-song"], args=[120.5, WINDOW, LIMIT, "late"])
    print("sliding window, 60 seconds later:", "allowed" if later else "blocked")
    print("keys left in Redis:", sorted(r.keys("rl:*")))
    print("redis-py", redis.__version__)
