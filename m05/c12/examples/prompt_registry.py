import hashlib
import json

import psycopg

DSN = "postgresql://anhti:anhti@localhost:55432/anhti"
SCHEMA = "m05_c12"


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()[:12]


with psycopg.connect(DSN, autocommit=True) as db:
    db.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
    db.execute(f"CREATE SCHEMA {SCHEMA}")
    db.execute(f"SET search_path TO {SCHEMA}")
    db.execute("CREATE TABLE prompt_versions (name text, version int, body text, sha text, PRIMARY KEY (name, version))")
    db.execute("CREATE TABLE release_pointer (name text PRIMARY KEY, stable int, canary int, canary_percent int)")
    db.execute("CREATE TABLE release_events (id serial PRIMARY KEY, name text, action text, detail jsonb, at timestamptz DEFAULT now())")

    def add(name, version, body):
        db.execute("INSERT INTO prompt_versions VALUES (%s, %s, %s, %s)", (name, version, body, sha(body)))

    def event(action, **detail):
        db.execute("INSERT INTO release_events (name, action, detail) VALUES ('chat_system', %s, %s)", (action, json.dumps(detail)))

    add("chat_system", 1, "Bạn là trợ lý chăm sóc khách hàng. Trả lời ngắn gọn.")
    add("chat_system", 2, "Bạn là trợ lý chăm sóc khách hàng. Trả lời ngắn gọn, luôn nêu bước tiếp theo.")
    db.execute("INSERT INTO release_pointer VALUES ('chat_system', 1, NULL, 0)")
    event("publish", stable=1)

    db.execute("UPDATE release_pointer SET canary = 2, canary_percent = 10 WHERE name = 'chat_system'")
    event("canary_start", version=2, percent=10, approved_by="Lan")

    db.execute("UPDATE release_pointer SET canary = NULL, canary_percent = 0 WHERE name = 'chat_system'")
    event("rollback", version=2, reason="score drop", diff=-0.107, t=-4.8)

    print("pointer:", db.execute("SELECT stable, canary, canary_percent FROM release_pointer").fetchone())
    print("versions:", db.execute("SELECT version, sha FROM prompt_versions ORDER BY version").fetchall())
    for action, detail in db.execute("SELECT action, detail FROM release_events ORDER BY id"):
        print("event:", action, detail)

    db.execute("UPDATE prompt_versions SET body = body || ' Hãy xưng em.' WHERE version = 2")
    drift = db.execute("SELECT version, sha, body FROM prompt_versions WHERE version = 2").fetchone()
    print("silent edit detected:", sha(drift[2]) != drift[1])
    db.execute(f"DROP SCHEMA {SCHEMA} CASCADE")
