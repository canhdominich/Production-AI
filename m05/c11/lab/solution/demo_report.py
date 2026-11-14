import sqlite3
import subprocess
import time

import redis

import secure_api as sa

NOW = 1_800_000_000
ring = sa.Keyring("k1", "signing-secret-k1-0123456789abcdef0123")
tok = sa.issue_token(ring, "br-cau-go", "cg-02", "branch_lead", NOW)
print("token claims   :", {k: v for k, v in sa.verify_token(ring, tok, NOW + 5).items() if k in ("sub", "tenant", "role")})
ring.rotate("k2", "signing-secret-k2-9876543210fedcba9876")
print("after rotate   : old token", "ok" if sa.verify_token(ring, tok, NOW + 6) else "bad", "| active key", ring.active)
ring.retire("k1")
try:
    sa.verify_token(ring, tok, NOW + 7)
except sa.AuthError as e:
    print("after retire   : old token rejected:", e)

kid, full = sa.new_api_key()
store = {kid: {"tenant": "br-ben-song", "hash": sa.hash_api_key(full)}}
print("api key        :", sa.verify_api_key(store, full), "| tampered:", sa.verify_api_key(store, full + "x"))

proc = subprocess.Popen(["redis-server", "--port", "5712", "--save", "", "--bind", "127.0.0.1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    r = redis.Redis(port=5712, protocol=2)
    for _ in range(50):
        try:
            r.ping()
            break
        except redis.ConnectionError:
            time.sleep(0.1)
    rl = sa.RateLimiter(r, 30)
    print("rate limit 30/min, 45 calls in one minute:", sum(rl.allow("br-ben-song", NOW) for _ in range(45)), "allowed")
finally:
    proc.terminate()
    proc.wait(timeout=10)

db = sqlite3.connect(":memory:")
db.executescript("""create table customers (customer_id text primary key, full_name text, phone text);
create table chat_messages (id integer primary key, customer_id text, body text);
create table customer_notes (id integer primary key, customer_id text, note text);
create table usage_events (id integer primary key, customer_id text, cost_usd real);
insert into customers values ('c-1','An Nguyen','0901234567');
insert into chat_messages values (1,'c-1','An Nguyen at 0901234567'),(2,'c-1','again');
insert into customer_notes values (1,'c-1','called 0901234567');
insert into usage_events values (1,'c-1',0.01),(2,'c-1',0.02);""")
print("residue before :", sa.find_residue(db, ["c-1", "0901234567"]))
print("erase counts   :", sa.erase_customer(db, "c-1"))
print("residue after  :", sa.find_residue(db, ["c-1", "0901234567"]))
