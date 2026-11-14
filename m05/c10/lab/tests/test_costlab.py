import os
import threading
from datetime import datetime, timezone

import psycopg
import pytest

import costlab
from costlab import (BudgetLedger, admit, budget_state, cost_matrix, create_table, downgrade, evaluate_policy, month_spend, record_usage,
                     token_cost)

DSN = os.environ.get("ANHTI_DSN", "host=localhost port=55432 dbname=anhti user=anhti password=anhti")
TABLE = "m05_c10.usage_events_lab"
START = datetime(2026, 10, 1, tzinfo=timezone.utc)
END = datetime(2026, 11, 1, tzinfo=timezone.utc)


@pytest.fixture()
def conn():
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute("CREATE SCHEMA IF NOT EXISTS m05_c10")
        create_table(c, TABLE)
        yield c
        c.execute(f"DROP TABLE IF EXISTS {TABLE}")


def event(i, tenant="br-cau-go", feature="chat", tier="small", cost=0.001, day=5, status="ok"):
    return dict(request_id=f"r{i}", ts=datetime(2026, 10, day, 9, 0, tzinfo=timezone.utc), tenant_id=tenant, feature=feature, tier=tier,
                status=status, prompt_tokens=100, output_tokens=50, cost_usd=cost)


def test_token_cost_splits_input_cached_and_output():
    assert token_cost("small", 1_000_000, 0) == pytest.approx(0.15)
    assert token_cost("small", 0, 1_000_000) == pytest.approx(0.60)
    assert token_cost("medium", 400, 120) == pytest.approx(0.00066)
    assert token_cost("medium", 400, 120, cached_tokens=300) == pytest.approx(0.000495)


def test_token_cost_rejects_bad_input():
    with pytest.raises(ValueError):
        token_cost("huge", 10, 10)
    with pytest.raises(ValueError):
        token_cost("small", 10, -1)
    with pytest.raises(ValueError):
        token_cost("small", 10, 10, cached_tokens=11)


def test_table_rejects_bad_rows(conn):
    with pytest.raises(psycopg.errors.CheckViolation):
        record_usage(conn, TABLE, event(1, tier="gigantic"))
    with pytest.raises(psycopg.errors.CheckViolation):
        record_usage(conn, TABLE, event(2, cost=-0.5))


def test_record_usage_is_idempotent(conn):
    assert record_usage(conn, TABLE, event(1)) is True
    assert record_usage(conn, TABLE, event(1)) is False
    assert conn.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0] == 1


def test_month_spend_respects_tenant_and_month_boundaries(conn):
    record_usage(conn, TABLE, event(1, cost=0.25))
    record_usage(conn, TABLE, event(2, cost=0.50, day=30))
    record_usage(conn, TABLE, event(3, tenant="br-ben-song", cost=9.0))
    nov = dict(event(4, cost=7.0), ts=datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc))
    record_usage(conn, TABLE, nov)
    assert month_spend(conn, TABLE, "br-cau-go", START, END) == pytest.approx(0.75)
    assert month_spend(conn, TABLE, "br-xom-vui", START, END) == 0.0


def test_cost_matrix_groups_by_tenant_and_feature(conn):
    record_usage(conn, TABLE, event(1, cost=0.1))
    record_usage(conn, TABLE, event(2, cost=0.2))
    record_usage(conn, TABLE, event(3, feature="weekly_report_agent", tier="large", cost=1.0))
    record_usage(conn, TABLE, event(4, tenant="br-ben-song", cost=0.4))
    m = cost_matrix(conn, TABLE, START, END)
    assert m[("br-cau-go", "chat")] == pytest.approx(0.3)
    assert m[("br-cau-go", "weekly_report_agent")] == pytest.approx(1.0)
    assert m[("br-ben-song", "chat")] == pytest.approx(0.4)
    assert len(m) == 3


def test_budget_state_thresholds():
    assert budget_state(10, 100) == "ok"
    assert budget_state(79.99, 100) == "ok"
    assert budget_state(80, 100) == "soft"
    assert budget_state(99.99, 100) == "soft"
    assert budget_state(100, 100) == "hard"
    assert budget_state(50, 100, soft_pct=40, hard_pct=60) == "soft"
    with pytest.raises(ValueError):
        budget_state(1, 0)


def test_downgrade_never_goes_below_the_feature_floor():
    assert downgrade("large", "chat") == "medium"
    assert downgrade("medium", "chat") == "small"
    assert downgrade("small", "chat") == "small"
    assert downgrade("large", "knowledge_assistant") == "medium"
    assert downgrade("medium", "knowledge_assistant") == "medium"
    assert downgrade("large", "weekly_report_agent") == "large"


def test_ledger_reserve_and_settle():
    ledger = BudgetLedger()
    assert ledger.reserve("a", 0.4, 1.0) is True
    assert ledger.reserve("a", 0.4, 1.0) is True
    assert ledger.reserve("a", 0.4, 1.0) is False
    assert ledger.spent("a") == pytest.approx(0.8)
    ledger.settle("a", -0.3)
    assert ledger.spent("a") == pytest.approx(0.5)
    assert ledger.spent("b") == 0.0


def test_ledger_never_overshoots_under_threads():
    ledger = BudgetLedger()
    results = []
    barrier = threading.Barrier(32)

    def worker():
        barrier.wait()
        results.append(ledger.reserve("a", 0.0625, 1.0))

    threads = [threading.Thread(target=worker) for _ in range(32)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sum(results) == 16
    assert ledger.spent("a") <= 1.0 + 1e-9


def test_admit_allows_downgrades_and_blocks():
    ledger = BudgetLedger()
    assert admit(ledger, "a", "chat", "medium", 0.1, 1.0) == ("allow", "medium")
    ledger.settle("a", 0.75)
    assert ledger.spent("a") == pytest.approx(0.85)
    assert admit(ledger, "a", "chat", "medium", 0.05, 1.0) == ("downgrade", "small")
    assert admit(ledger, "a", "weekly_report_agent", "large", 0.05, 1.0) == ("allow", "large")
    ledger.settle("a", 0.1)
    assert admit(ledger, "a", "chat", "small", 0.2, 1.0)[0] == "block"
    assert admit(ledger, "other", "chat", "small", 0.2, 1.0) == ("allow", "small")


def test_blocked_request_does_not_consume_budget():
    ledger = BudgetLedger()
    ledger.settle("a", 0.95)
    spent = ledger.spent("a")
    assert admit(ledger, "a", "chat", "small", 0.2, 1.0)[0] == "block"
    assert ledger.spent("a") == spent


TASKS = [
    dict(fast_correct=1, deep_correct=1, fast_cost=0.001, deep_cost=0.01),
    dict(fast_correct=0, deep_correct=1, fast_cost=0.001, deep_cost=0.01),
    dict(fast_correct=1, deep_correct=1, fast_cost=0.001, deep_cost=0.01),
    dict(fast_correct=0, deep_correct=0, fast_cost=0.001, deep_cost=0.01),
]


def test_evaluate_policy_for_fixed_choices():
    acc, cost = evaluate_policy(TASKS, lambda t: "fast")
    assert acc == pytest.approx(0.5) and cost == pytest.approx(1.0)
    acc, cost = evaluate_policy(TASKS, lambda t: "deep")
    assert acc == pytest.approx(0.75) and cost == pytest.approx(10.0)


def test_evaluate_policy_cascade_pays_for_both_calls():
    acc, cost = evaluate_policy(TASKS, lambda t: "cascade")
    assert acc == pytest.approx(0.75) and cost == pytest.approx(11.0)
    acc, cost = evaluate_policy(TASKS, lambda t: "deep" if not t["fast_correct"] else "fast")
    assert acc == pytest.approx(0.75) and cost == pytest.approx(5.5)


def test_evaluate_policy_rejects_bad_input():
    with pytest.raises(ValueError):
        evaluate_policy([], lambda t: "fast")
    with pytest.raises(ValueError):
        evaluate_policy(TASKS, lambda t: "medium")
