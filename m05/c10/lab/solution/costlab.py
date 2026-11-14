import threading

PRICES = {
    "small": {"input": 0.15, "cached": 0.04, "output": 0.60},
    "medium": {"input": 0.75, "cached": 0.20, "output": 3.00},
    "large": {"input": 5.00, "cached": 1.25, "output": 20.00},
}
TIERS = ("small", "medium", "large")
MIN_TIER = {"chat": "small", "knowledge_assistant": "medium", "weekly_report_agent": "large"}


def token_cost(tier, prompt_tokens, output_tokens, cached_tokens=0):
    if tier not in PRICES:
        raise ValueError(f"unknown tier {tier!r}")
    if min(prompt_tokens, output_tokens, cached_tokens) < 0 or cached_tokens > prompt_tokens:
        raise ValueError("token counts must be non-negative and cached tokens cannot exceed prompt tokens")
    p = PRICES[tier]
    fresh = prompt_tokens - cached_tokens
    return (fresh * p["input"] + cached_tokens * p["cached"] + output_tokens * p["output"]) / 1_000_000


def create_table(conn, table):
    conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.execute(f"""
        CREATE TABLE {table} (
            request_id    text PRIMARY KEY,
            ts            timestamptz NOT NULL,
            tenant_id     text NOT NULL,
            feature       text NOT NULL,
            tier          text NOT NULL CHECK (tier IN ('small', 'medium', 'large')),
            status        text NOT NULL,
            prompt_tokens int NOT NULL DEFAULT 0 CHECK (prompt_tokens >= 0),
            output_tokens int NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),
            cost_usd      numeric(14, 8) NOT NULL DEFAULT 0 CHECK (cost_usd >= 0)
        )""")
    conn.execute(f"CREATE INDEX ON {table} (tenant_id, ts)")


def record_usage(conn, table, event):
    cur = conn.execute(
        f"INSERT INTO {table} (request_id, ts, tenant_id, feature, tier, status, prompt_tokens, output_tokens, cost_usd) "
        "VALUES (%(request_id)s, %(ts)s, %(tenant_id)s, %(feature)s, %(tier)s, %(status)s, %(prompt_tokens)s, %(output_tokens)s, %(cost_usd)s) "
        "ON CONFLICT (request_id) DO NOTHING", event)
    return cur.rowcount == 1


def month_spend(conn, table, tenant_id, start, end):
    row = conn.execute(f"SELECT coalesce(sum(cost_usd), 0) FROM {table} WHERE tenant_id = %s AND ts >= %s AND ts < %s", (tenant_id, start, end)).fetchone()
    return float(row[0])


def cost_matrix(conn, table, start, end):
    rows = conn.execute(f"SELECT tenant_id, feature, sum(cost_usd) FROM {table} WHERE ts >= %s AND ts < %s GROUP BY 1, 2", (start, end)).fetchall()
    return {(t, f): float(c) for t, f, c in rows}


def budget_state(spent, budget, soft_pct=80, hard_pct=100):
    if budget <= 0:
        raise ValueError("budget must be positive")
    ratio = spent / budget * 100
    if ratio >= hard_pct:
        return "hard"
    return "soft" if ratio >= soft_pct else "ok"


def downgrade(tier, feature):
    floor = TIERS.index(MIN_TIER[feature])
    return TIERS[max(floor, TIERS.index(tier) - 1)]


class BudgetLedger:
    def __init__(self):
        self._spent = {}
        self._lock = threading.Lock()

    def spent(self, tenant_id):
        with self._lock:
            return self._spent.get(tenant_id, 0.0)

    def reserve(self, tenant_id, estimate, limit):
        with self._lock:
            now = self._spent.get(tenant_id, 0.0)
            if now + estimate > limit:
                return False
            self._spent[tenant_id] = now + estimate
            return True

    def settle(self, tenant_id, delta):
        with self._lock:
            self._spent[tenant_id] = self._spent.get(tenant_id, 0.0) + delta


def admit(ledger, tenant_id, feature, tier, estimate, budget):
    state = budget_state(ledger.spent(tenant_id), budget)
    decision = "allow"
    if state == "soft":
        new = downgrade(tier, feature)
        if new != tier:
            tier, decision = new, "downgrade"
    if not ledger.reserve(tenant_id, estimate, budget):
        return "block", tier
    return decision, tier


def evaluate_policy(tasks, decide):
    if not tasks:
        raise ValueError("no tasks")
    correct, cost = 0, 0.0
    for t in tasks:
        choice = decide(t)
        if choice == "fast":
            correct += t["fast_correct"]
            cost += t["fast_cost"]
        elif choice == "deep":
            correct += t["deep_correct"]
            cost += t["deep_cost"]
        elif choice == "cascade":
            correct += t["deep_correct"]
            cost += t["fast_cost"] + t["deep_cost"]
        else:
            raise ValueError(f"unknown choice {choice!r}")
    return correct / len(tasks), cost / len(tasks) * 1000
