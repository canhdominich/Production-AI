import threading
from collections import defaultdict, deque


class RateLimited(Exception):
    status = 429

    def __init__(self, retry_after):
        super().__init__(f"rate limited, retry after {retry_after:.0f}s")
        self.retry_after = retry_after


class SlidingWindowLimiter:
    """Giữ mốc thời gian của từng khóa trong 60 giây gần nhất."""

    def __init__(self, window_s=60.0):
        self.window_s = window_s
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key, limit, now):
        # TODO 4: bỏ mốc cũ hơn window_s, từ chối khi đã đủ limit và trả số giây phải chờ, nếu không thì ghi mốc mới
        return True, 0.0


class RedisWindowLimiter:
    """Cửa sổ cố định theo phút, dùng chung cho nhiều tiến trình API."""

    def __init__(self, client, window_s=60):
        self.client = client
        self.window_s = window_s

    def allow(self, key, limit, now):
        slot = int(now // self.window_s)
        name = f"rl:{key}:{slot}"
        pipe = self.client.pipeline()
        pipe.incr(name)
        pipe.expire(name, self.window_s * 2)
        count = pipe.execute()[0]
        if count > limit:
            return False, float(self.window_s - (now % self.window_s))
        return True, 0.0
