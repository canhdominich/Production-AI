import hashlib
import math
import statistics
from pathlib import Path

REQUIRED_SECTIONS = ["identity", "intended_use", "out_of_scope", "data_sources", "evaluation", "limitations", "oversight", "config_digest"]
HONEST_LABELS = ("Đã chạy", "Minh họa")


def bucket(user_id, salt, buckets=100):
    # TODO 1: băm f"{salt}:{user_id}" bằng sha256, lấy 8 ký tự hex đầu, đổi sang số nguyên rồi chia dư cho buckets
    raise NotImplementedError


def route(user_id, percent, salt="release"):
    # TODO 2: trả "canary" nếu bucket nhỏ hơn percent, ngược lại "stable"
    raise NotImplementedError


def welch_t(a, b):
    # TODO 3: (mean(a) - mean(b)) / sqrt(var(a)/len(a) + var(b)/len(b)); trả 0.0 khi thiếu mẫu hoặc se bằng 0
    raise NotImplementedError


class CanaryController:
    def __init__(self, margin=0.05, z=2.33, min_samples=30, strikes=2):
        self.margin, self.z, self.min_samples, self.strikes = margin, z, min_samples, strikes
        self.bad_windows = 0

    def observe(self, stable, canary):
        # TODO 4: "wait" nếu canary ít hơn min_samples; "watch" ở cửa sổ xấu đầu tiên; "rollback" khi đủ strikes cửa sổ xấu liên tiếp; "ok" và xóa bộ đếm khi không xấu
        # cửa sổ xấu: trung bình canary thấp hơn stable quá margin VÀ welch_t(canary, stable) nhỏ hơn -z
        raise NotImplementedError


class CanaryRun:
    def __init__(self, controller=None, promote_after=6):
        self.controller = controller or CanaryController()
        self.promote_after = promote_after
        self.ok_windows = 0
        self.status = "running"
        self.history = []

    def step(self, stable, canary):
        # TODO 5: sau khi đã rolled_back hoặc promoted thì không đổi nữa; ngược lại hỏi controller, ghi vào history,
        # rollback thì status thành "rolled_back", đủ promote_after cửa sổ "ok" thì thành "promoted"
        raise NotImplementedError


def validate_card(card):
    # TODO 6: trả danh sách lỗi (chuỗi); kiểm các mục trong REQUIRED_SECTIONS, ít nhất 3 giới hạn mỗi giới hạn từ 5 từ,
    # mỗi evaluation có dataset và label thuộc HONEST_LABELS, mỗi data source có origin, owner, license
    raise NotImplementedError


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def stale_files(card, paths):
    # TODO 7: trả danh sách tên tệp (đã sắp xếp) mà dấu vân tay trong card["config_digest"] khác file_digest hiện tại hoặc chưa có
    raise NotImplementedError
