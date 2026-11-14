import math
import random
import time
from dataclasses import dataclass, field

RETRYABLE = {"timeout", "rate_limit", "server_error", "connection"}


class ProviderFailure(Exception):
    def __init__(self, kind, status_code=None, retry_after=None):
        super().__init__(f"{kind} ({status_code})")
        self.kind = kind
        self.status_code = status_code
        self.retry_after = retry_after


class AllProvidersFailed(Exception):
    def __init__(self, attempts, reason="exhausted"):
        super().__init__(f"{reason} after {len(attempts)} attempts")
        self.attempts = attempts
        self.reason = reason


@dataclass
class CallResult:
    value: object
    provider: str
    attempts: int
    fallback_used: bool
    waited_s: float = 0.0
    log: list = field(default_factory=list)


def is_retryable(error):
    # TODO 1: True khi error có thuộc tính kind nằm trong RETRYABLE; lỗi không có kind thì False
    raise NotImplementedError


def backoff_delay(attempt, base=0.5, cap=8.0, jitter="full", rnd=None):
    # TODO 2: ceiling = min(cap, base * 2 ** attempt); jitter "none" trả ceiling, "full" trả số ngẫu nhiên đều trong [0, ceiling]
    raise NotImplementedError


def retry_wait(error, attempt, base=0.5, cap=8.0, rnd=None):
    # TODO 3: lỗi rate_limit có retry_after thì chờ retry_after cộng thêm rnd.random() * base (Retry-After là mức tối thiểu); còn lại dùng backoff_delay full jitter
    raise NotImplementedError


class CircuitBreaker:
    def __init__(self, failure_threshold=5, cooldown_s=30.0, half_open_max=1, clock=time.monotonic):
        self.failure_threshold = failure_threshold
        self.cooldown_s = cooldown_s
        self.half_open_max = half_open_max
        self.clock = clock
        self._state = "closed"
        self._failures = 0
        self._opened_at = 0.0
        self._probes = 0
        self.transitions = []

    def _move(self, state):
        self._state = state
        self.transitions.append((round(self.clock(), 3), state))

    @property
    def state(self):
        # TODO 4: nếu đang open và đã qua cooldown_s kể từ _opened_at thì đặt _probes = 0, chuyển sang half_open (dùng _move)
        return self._state

    def allow(self):
        # TODO 5: closed cho qua; open chặn; half_open chỉ cho tối đa half_open_max lần thử (đếm vào _probes)
        raise NotImplementedError

    def record_success(self):
        # TODO 6: half_open thành công thì đóng mạch và xóa đếm lỗi; closed thành công thì xóa đếm lỗi liên tiếp
        raise NotImplementedError

    def record_failure(self):
        # TODO 7: half_open thất bại thì mở lại (ghi _opened_at); closed thì tăng _failures và mở khi đạt failure_threshold
        raise NotImplementedError


class ResilientCaller:
    def __init__(self, providers, breakers=None, max_attempts=3, base=0.5, cap=8.0, deadline_s=20.0,
                 clock=time.monotonic, sleep=time.sleep, rnd=None):
        self.providers = providers
        self.breakers = breakers or {name: CircuitBreaker(clock=clock) for name, _ in providers}
        self.max_attempts = max_attempts
        self.base, self.cap, self.deadline_s = base, cap, deadline_s
        self.clock, self.sleep = clock, sleep
        self.rnd = rnd or random.Random(0)

    def call(self, request):
        # TODO 8: duyệt providers theo thứ tự; mỗi provider thử tối đa max_attempts lần.
        #   - hết deadline_s thì raise AllProvidersFailed(log, "deadline")
        #   - breaker.allow() sai thì ghi (name, "circuit_open") và sang provider kế
        #   - fn(request, remaining) lỗi có kind: ghi (name, kind); bad_request không tính vào breaker và raise ngay;
        #     lỗi khác tính breaker.record_failure(); nếu retry_wait lớn hơn cap thì ghi (name, "retry_after_too_long") và sang provider kế;
        #     không thì chờ retry_wait (không vượt thời gian còn lại) trước lần thử kế
        #   - thành công thì breaker.record_success() và trả CallResult(value, name, số lần gọi thật, name khác provider đầu, waited, log)
        #   - hết cả chuỗi thì raise AllProvidersFailed(log)
        raise NotImplementedError


def error_budget(slo, total_events):
    # TODO 9: số sự kiện xấu tối đa được phép = floor(total_events * (1 - slo)); làm tròn trung gian 6 chữ số để tránh lỗi số thực
    raise NotImplementedError


def downtime_minutes(slo, days=30):
    # TODO 10: số phút ngừng được phép trong days ngày, làm tròn 2 chữ số
    raise NotImplementedError


def budget_status(slo, total_events, bad_events):
    # TODO 11: trả dict allowed, bad, remaining (có thể âm), burned (bad / allowed, làm tròn 4 chữ số)
    raise NotImplementedError


def compute_slis(records, latency_ms):
    # TODO 12: bỏ bản ghi status "bad_request"; availability = ok / tất cả; latency = ok và latency_ms nhỏ hơn hoặc bằng ngưỡng / ok;
    #   quality = ok có finish_reason "stop" (mặc định "stop") / ok; không còn bản ghi nào thì ValueError
    raise NotImplementedError
