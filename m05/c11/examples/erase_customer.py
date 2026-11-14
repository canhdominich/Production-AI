import hashlib
import hmac
import redis
from _sec import PORT_REDIS, SCHEMA, pg, redis_server

conn = pg()
for t in ("chat_messages", "customer_vectors", "usage_events", "customers"):
    conn.execute(f"drop table if exists {t} cascade")
conn.execute("create table customers (customer_id text primary key, tenant_id text, full_name text, phone text, created date)")
conn.execute("create table chat_messages (id serial primary key, customer_id text references customers, tenant_id text, body text)")
conn.execute("create table usage_events (id serial primary key, customer_id text, tenant_id text, cost_usd numeric)")
conn.execute("create table customer_vectors (id serial primary key, customer_id text, chunk text, embedding vector(4))")

TENANTS = ["br-dau-pho", "br-cau-go", "br-ben-song"]
for i in range(60):
    cid, name, phone = f"c-{i:05d}", f"Customer {i}", f"09{i * 1234567 % 100000000:08d}"
    conn.execute("insert into customers values (%s,%s,%s,%s,%s)", (cid, TENANTS[i % 3], name, phone, "2025-01-01" if i % 5 == 0 else "2026-10-01"))
    for k in range(3):
        conn.execute("insert into chat_messages (customer_id, tenant_id, body) values (%s,%s,%s)", (cid, TENANTS[i % 3], f"{name} asks about order {k}, call {phone}"))
        conn.execute("insert into usage_events (customer_id, tenant_id, cost_usd) values (%s,%s,%s)", (cid, TENANTS[i % 3], 0.002 * (k + 1)))
    conn.execute("insert into customer_vectors (customer_id, chunk, embedding) values (%s,%s,%s)", (cid, f"profile note of {name}, phone {phone}", f"[{i % 7},1,0,{i % 3}]"))

TARGET = "c-00007"
target = conn.execute("select full_name, phone, tenant_id from customers where customer_id=%s", (TARGET,)).fetchone()
name, phone, tenant = target
PEPPER = b"demo-pepper-not-a-real-secret"


def residue(r):
    found = {}
    for tbl, cols in (("customers", ("customer_id", "full_name", "phone")), ("chat_messages", ("customer_id", "body")),
                      ("usage_events", ("customer_id",)), ("customer_vectors", ("customer_id", "chunk"))):
        n = 0
        for col in cols:
            for needle in (TARGET, name, phone):
                n += conn.execute(f"select count(*) from {tbl} where {col}::text like %s", (f"%{needle}%",)).fetchone()[0]
        if n:
            found[tbl] = n
    keys = [k.decode() for k in r.scan_iter("cache:*")]
    hits = [k for k in keys if TARGET in k or any(needle in (r.get(k) or b"").decode() for needle in (name, phone))]
    if hits:
        found["redis"] = len(hits)
    return found


def erase(r, full=True):
    with conn.transaction():
        conn.execute("delete from chat_messages where customer_id=%s", (TARGET,))
        conn.execute("update usage_events set customer_id = null where customer_id=%s", (TARGET,))
        conn.execute("delete from customers where customer_id=%s", (TARGET,))
        if full:
            conn.execute("delete from customer_vectors where customer_id=%s", (TARGET,))
    if full:
        for k in list(r.scan_iter(f"cache:{tenant}:{TARGET}:*")):
            r.delete(k)
        for k in list(r.scan_iter("cache:*")):
            if name.encode() in (r.get(k) or b""):
                r.delete(k)
    return hmac.new(PEPPER, TARGET.encode(), hashlib.sha256).hexdigest()[:16]


with redis_server() as port:
    r = redis.Redis(port=port, protocol=2)
    r.set(f"cache:{tenant}:{TARGET}:last-answer", f"Hello {name}, we will call {phone}")
    r.set(f"cache:{tenant}:shared:faq", f"Shipping is free; asked by {name}")
    r.set(f"cache:{tenant}:c-00008:last-answer", "Hello Customer 8")
    print("before erase, rows mentioning the customer:", residue(r))
    ref = erase(r, full=False)
    print("erase without vectors and cache  :", residue(r))
    ref = erase(r, full=True)
    print("erase of every store             :", residue(r) or "nothing left")
    print("audit reference (hmac, not the id):", ref)
    print("usage_events kept for accounting :", conn.execute("select count(*), round(sum(cost_usd), 3) from usage_events where customer_id is null").fetchone())
    print("other customers untouched        :", conn.execute("select count(*) from customers").fetchone()[0], "customers,", conn.execute("select count(*) from chat_messages").fetchone()[0], "messages")
    old = conn.execute("select count(*) from customers where created < date '2026-01-01'").fetchone()[0]
    conn.execute("delete from chat_messages where customer_id in (select customer_id from customers where created < date '2026-01-01')")
    print("retention: customers older than 2026:", old, "| their messages purged:", conn.execute("select count(*) from chat_messages c join customers u using (customer_id) where u.created < date '2026-01-01'").fetchone()[0], "left")
for t in ("chat_messages", "customer_vectors", "usage_events", "customers"):
    conn.execute(f"drop table if exists {t} cascade")
