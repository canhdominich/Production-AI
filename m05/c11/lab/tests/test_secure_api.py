import sqlite3
import subprocess
import threading
import time

import jwt
import pytest
import redis

import secure_api as sa

NOW = 1_800_000_000
PORT = 5712


@pytest.fixture(scope="module")
def redis_client():
    proc = subprocess.Popen(["redis-server", "--port", str(PORT), "--save", "", "--appendonly", "no", "--bind", "127.0.0.1"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    r = redis.Redis(port=PORT, protocol=2)
    for _ in range(50):
        try:
            r.ping()
            break
        except redis.ConnectionError:
            time.sleep(0.1)
    yield r
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture
def ring():
    return sa.Keyring("k1", "signing-secret-k1-0123456789abcdef0123")


def forge(secret, kid="k1", **over):
    claims = {"iss": sa.ISSUER, "aud": sa.AUDIENCE, "sub": "u1", "tenant": "br-cau-go", "role": "branch_lead", "iat": NOW, "exp": NOW + 900}
    claims.update(over)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, secret, algorithm="HS256", headers={"kid": kid})


def test_valid_token_returns_claims(ring):
    c = sa.verify_token(ring, sa.issue_token(ring, "br-cau-go", "cg-02", "branch_lead", NOW), NOW + 10)
    assert (c["tenant"], c["sub"], c["role"]) == ("br-cau-go", "cg-02", "branch_lead")


def test_expired_token_is_rejected(ring):
    tok = sa.issue_token(ring, "br-cau-go", "cg-02", "branch_lead", NOW, ttl=900)
    with pytest.raises(sa.AuthError, match="expired"):
        sa.verify_token(ring, tok, NOW + 900)
    assert sa.verify_token(ring, tok, NOW + 899)


def test_edited_payload_is_rejected(ring):
    h, b, s = sa.issue_token(ring, "br-cau-go", "cg-02", "branch_lead", NOW).split(".")
    other = sa.issue_token(ring, "br-dau-pho", "cg-02", "branch_lead", NOW).split(".")[1]
    with pytest.raises(sa.AuthError):
        sa.verify_token(ring, f"{h}.{other}.{s}", NOW + 1)


def test_token_without_tenant_claim_is_rejected(ring):
    with pytest.raises(sa.AuthError):
        sa.verify_token(ring, forge(ring.keys["k1"], tenant=None), NOW + 1)
    with pytest.raises(sa.AuthError):
        sa.verify_token(ring, forge(ring.keys["k1"], tenant=""), NOW + 1)


def test_wrong_audience_issuer_and_alg_none(ring):
    with pytest.raises(sa.AuthError):
        sa.verify_token(ring, forge(ring.keys["k1"], aud="other"), NOW + 1)
    with pytest.raises(sa.AuthError):
        sa.verify_token(ring, forge(ring.keys["k1"], iss="evil"), NOW + 1)
    unsigned = jwt.encode({"sub": "u1", "tenant": "br-cau-go", "role": "branch_manager"}, None, algorithm="none", headers={"kid": "k1"})
    with pytest.raises(sa.AuthError):
        sa.verify_token(ring, unsigned, NOW + 1)


def test_unknown_kid_and_garbage(ring):
    with pytest.raises(sa.AuthError, match="unknown_kid"):
        sa.verify_token(ring, forge(ring.keys["k1"], kid="k9"), NOW + 1)
    with pytest.raises(sa.AuthError):
        sa.verify_token(ring, "not-a-token", NOW + 1)


def test_rotation_overlap_then_retire(ring):
    old = sa.issue_token(ring, "br-cau-go", "cg-02", "branch_lead", NOW)
    ring.rotate("k2", "signing-secret-k2-9876543210fedcba9876")
    new = sa.issue_token(ring, "br-cau-go", "cg-02", "branch_lead", NOW + 5)
    assert jwt.get_unverified_header(new)["kid"] == "k2"
    assert sa.verify_token(ring, old, NOW + 10)["tenant"] == "br-cau-go"
    assert sa.verify_token(ring, new, NOW + 10)["tenant"] == "br-cau-go"
    ring.retire("k1")
    with pytest.raises(sa.AuthError, match="unknown_kid"):
        sa.verify_token(ring, old, NOW + 10)
    assert sa.verify_token(ring, new, NOW + 10)
    with pytest.raises(ValueError):
        ring.retire("k2")


def test_api_key_is_stored_hashed_and_verified():
    store = {}
    kid, full = sa.new_api_key()
    store[kid] = {"tenant": "br-cau-go", "hash": sa.hash_api_key(full)}
    assert full.startswith(f"gd_{kid}_")
    assert full not in str(store) and len(store[kid]["hash"]) == 64
    assert sa.verify_api_key(store, full) == "br-cau-go"
    assert sa.verify_api_key(store, full[:-1] + ("A" if full[-1] != "A" else "B")) is None
    assert sa.verify_api_key(store, "gd_ffffffff_" + full.split("_", 2)[2]) is None
    assert sa.verify_api_key(store, "garbage") is None
    assert sa.verify_api_key(store, "") is None
    store[kid]["revoked"] = True
    assert sa.verify_api_key(store, full) is None


def test_api_keys_are_unique():
    assert len({sa.new_api_key()[1] for _ in range(50)}) == 50


def test_rate_limit_per_tenant_and_window(redis_client):
    redis_client.flushall()
    rl = sa.RateLimiter(redis_client, 30)
    assert sum(rl.allow("br-ben-song", NOW + i * 0.1) for i in range(40)) == 30
    assert rl.allow("br-cau-go", NOW)
    assert rl.allow("br-ben-song", NOW + 61)


def test_rate_limit_is_atomic_under_threads(redis_client):
    redis_client.flushall()
    rl = sa.RateLimiter(redis_client, 50)
    results, lock = [], threading.Lock()

    def work():
        local = [rl.allow("br-dau-pho", NOW) for _ in range(20)]
        with lock:
            results.extend(local)
    ts = [threading.Thread(target=work) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sum(results) == 50


def test_rate_limit_counter_expires(redis_client):
    redis_client.flushall()
    sa.RateLimiter(redis_client, 5).allow("br-cau-go", NOW)
    assert 0 < redis_client.ttl(f"rl:br-cau-go:{NOW // 60}") <= 120


@pytest.fixture
def db():
    c = sqlite3.connect(":memory:")
    c.executescript("""
        create table customers (customer_id text primary key, full_name text, phone text);
        create table chat_messages (id integer primary key, customer_id text, body text);
        create table customer_notes (id integer primary key, customer_id text, note text);
        create table usage_events (id integer primary key, customer_id text, cost_usd real);
        insert into customers values ('c-1','An Nguyen','0901234567'),('c-2','Binh Tran','0907654321');
        insert into chat_messages values (1,'c-1','An Nguyen at 0901234567 asks'),(2,'c-1','again'),(3,'c-2','Binh Tran asks');
        insert into customer_notes values (1,'c-1','called 0901234567'),(2,'c-2','vip');
        insert into usage_events values (1,'c-1',0.01),(2,'c-1',0.02),(3,'c-2',0.03);
    """)
    return c


def test_erase_customer_removes_personal_rows_and_keeps_accounting(db):
    counts = sa.erase_customer(db, "c-1")
    assert counts == {"chat_messages": 2, "customer_notes": 1, "usage_events": 2, "customers": 1}
    assert sa.find_residue(db, ["c-1", "An Nguyen", "0901234567"]) == {}
    assert db.execute("select round(sum(cost_usd), 2) from usage_events").fetchone()[0] == 0.06
    assert db.execute("select count(*) from customers where customer_id = 'c-2'").fetchone()[0] == 1
    assert db.execute("select count(*) from chat_messages").fetchone()[0] == 1


def test_find_residue_reports_table_and_column(db):
    found = sa.find_residue(db, ["0901234567"])
    assert found == {("customers", "phone"): 1, ("chat_messages", "body"): 1, ("customer_notes", "note"): 1}


def test_erase_unknown_customer_is_a_noop(db):
    assert sa.erase_customer(db, "c-99") == {"chat_messages": 0, "customer_notes": 0, "usage_events": 0, "customers": 0}
