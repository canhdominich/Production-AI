import threading

PRICES = {
    "small": {"input": 0.15, "cached": 0.04, "output": 0.60},
    "medium": {"input": 0.75, "cached": 0.20, "output": 3.00},
    "large": {"input": 5.00, "cached": 1.25, "output": 20.00},
}
TIERS = ("small", "medium", "large")
MIN_TIER = {"chat": "small", "knowledge_assistant": "medium", "weekly_report_agent": "large"}


def token_cost(tier, prompt_tokens, output_tokens, cached_tokens=0):
    # TODO 1: ném ValueError khi tier lạ, số token âm hoặc cached_tokens lớn hơn prompt_tokens;
    # tính đô la = (token mới x giá input + token cache x giá cached + token đầu ra x giá output) / 1 triệu
    raise NotImplementedError


def create_table(conn, table):
    # TODO 2: xóa bảng cũ nếu có, tạo bảng usage với khóa chính request_id, CHECK tier và các cột token, cost không âm, thêm chỉ mục (tenant_id, ts)
    raise NotImplementedError


def record_usage(conn, table, event):
    # TODO 3: chèn một dòng; trùng request_id thì bỏ qua và trả False, chèn được thì trả True
    raise NotImplementedError


def month_spend(conn, table, tenant_id, start, end):
    # TODO 4: tổng cost_usd của một tenant trong nửa khoảng [start, end), trả float, 0.0 khi không có dòng nào
    raise NotImplementedError


def cost_matrix(conn, table, start, end):
    # TODO 5: trả dict {(tenant_id, feature): tổng cost_usd} trong [start, end)
    raise NotImplementedError


def budget_state(spent, budget, soft_pct=80, hard_pct=100):
    # TODO 6: trả "ok", "soft" hoặc "hard" theo tỉ lệ đã dùng; ném ValueError khi budget không dương
    raise NotImplementedError


def downgrade(tier, feature):
    # TODO 7: hạ xuống một bậc nhưng không thấp hơn MIN_TIER của tính năng
    raise NotImplementedError


class BudgetLedger:
    def __init__(self):
        self._spent = {}
        self._lock = threading.Lock()

    def spent(self, tenant_id):
        # TODO 8a: số tiền đã dùng hoặc đã giữ chỗ của tenant, 0.0 nếu chưa có
        raise NotImplementedError

    def reserve(self, tenant_id, estimate, limit):
        # TODO 8b: kiểm tra và cộng trong cùng một đoạn có khóa; vượt limit thì trả False và không cộng gì
        raise NotImplementedError

    def settle(self, tenant_id, delta):
        # TODO 8c: cộng delta (có thể âm) vào số đã dùng
        raise NotImplementedError


def admit(ledger, tenant_id, feature, tier, estimate, budget):
    # TODO 9: ở trạng thái soft hạ tier (decision "downgrade" nếu tier thực sự đổi), rồi giữ chỗ;
    # giữ chỗ thất bại thì trả ("block", tier); còn lại trả (decision, tier) với decision "allow" hoặc "downgrade"
    raise NotImplementedError


def evaluate_policy(tasks, decide):
    # TODO 10: decide(task) trả "fast", "deep" hoặc "cascade"; cascade tốn fast_cost + deep_cost và dùng đáp án của deep;
    # trả (độ chính xác, chi phí trên 1000 yêu cầu); ném ValueError khi không có task hoặc lựa chọn lạ
    raise NotImplementedError
