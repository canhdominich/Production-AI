import random

import psycopg

from _kit import JUDGE_TNR, JUDGE_TPR, day_log, unit_hash

RATES = {"chat": 0.010, "knowledge_assistant": 0.030, "weekly_report_agent": 0.17}
DSN = "postgresql://anhti:anhti@localhost:55432/anhti"
rnd = random.Random(31)

with psycopg.connect(DSN, autocommit=True) as conn:
    conn.execute("DROP SCHEMA IF EXISTS m05_c14 CASCADE")
    conn.execute("CREATE SCHEMA m05_c14")
    conn.execute("""CREATE TABLE m05_c14.eval_samples (
        request_id text PRIMARY KEY, day int NOT NULL, feature text NOT NULL, tenant_id text NOT NULL,
        verdict boolean NOT NULL, judge_version text NOT NULL, prompt_version text NOT NULL)""")
    rows = []
    for day in range(1, 15):
        override = {"knowledge_assistant": 0.60} if day >= 8 else None
        for r in day_log(day, pass_override=override):
            if unit_hash(r["id"]) < RATES[r["feature"]] * 2:
                says_pass = rnd.random() < (JUDGE_TPR if r["good"] else 1 - JUDGE_TNR)
                rows.append((r["id"], day, r["feature"], r["tenant"], says_pass, "judge-v1", "kb-prompt-v3"))
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO m05_c14.eval_samples VALUES (%s,%s,%s,%s,%s,%s,%s)", rows)
    print(f"stored {len(rows)} judged samples for 14 days (about {len(rows) // 14} per day)")
    q = """
    WITH daily AS (
      SELECT day, count(*) AS n, count(*) FILTER (WHERE verdict) AS passed
      FROM m05_c14.eval_samples WHERE feature = 'knowledge_assistant' GROUP BY day)
    SELECT day, n, passed,
           sum(n) OVER w AS n3, round((sum(passed) OVER w)::numeric / sum(n) OVER w, 3) AS pass3
    FROM daily WINDOW w AS (ORDER BY day ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) ORDER BY day"""
    print("knowledge_assistant, daily samples and 3-day rolling pass rate:")
    for day, n, passed, n3, pass3 in conn.execute(q):
        print(f"day {day:2}: n={n:2} passed={passed:2}  rolling n={n3:2} pass={pass3}")
    conn.execute("DROP SCHEMA m05_c14 CASCADE")
