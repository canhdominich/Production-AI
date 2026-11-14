import hashlib
import hmac
import secrets

import jwt

ISSUER = "anhti-api"
AUDIENCE = "anhti-ai"
REQUIRED = ["exp", "iat", "sub", "tenant", "role"]


class AuthError(Exception):
    pass


class Keyring:
    def __init__(self, kid, secret):
        self.keys = {kid: secret}
        self.active = kid

    def rotate(self, new_kid, new_secret):
        self.keys[new_kid] = new_secret
        self.active = new_kid

    def retire(self, kid):
        if kid == self.active:
            raise ValueError("cannot retire the active key")
        self.keys.pop(kid, None)


def issue_token(ring, tenant, user, role, now, ttl=900):
    claims = {"iss": ISSUER, "aud": AUDIENCE, "sub": user, "tenant": tenant, "role": role, "iat": int(now), "exp": int(now) + ttl}
    return jwt.encode(claims, ring.keys[ring.active], algorithm="HS256", headers={"kid": ring.active})


def verify_token(ring, token, now):
    try:
        kid = jwt.get_unverified_header(token).get("kid")
        key = ring.keys.get(kid)
        if key is None:
            raise AuthError("unknown_kid")
        claims = jwt.decode(token, key, algorithms=["HS256"], audience=AUDIENCE, issuer=ISSUER,
                            options={"require": REQUIRED, "verify_exp": False, "verify_iat": False, "verify_nbf": False})
    except jwt.InvalidTokenError as e:
        raise AuthError(type(e).__name__) from None
    if claims["exp"] <= now:
        raise AuthError("expired")
    if not claims["tenant"]:
        raise AuthError("empty_tenant")
    return claims


def new_api_key():
    key_id = secrets.token_hex(4)
    return key_id, f"gd_{key_id}_{secrets.token_urlsafe(32)}"


def hash_api_key(full_key):
    return hashlib.sha256(full_key.encode()).hexdigest()


def verify_api_key(store, presented):
    parts = presented.split("_", 2)
    if len(parts) != 3 or parts[0] != "gd":
        return None
    row = store.get(parts[1])
    if row is None or row.get("revoked"):
        return None
    if not hmac.compare_digest(row["hash"], hash_api_key(presented)):
        return None
    return row["tenant"]


class RateLimiter:
    def __init__(self, client, limit_per_minute):
        self.r = client
        self.limit = limit_per_minute

    def allow(self, tenant, now):
        key = f"rl:{tenant}:{int(now // 60)}"
        n = self.r.incr(key)
        if n == 1:
            self.r.expire(key, 120)
        return n <= self.limit


TABLES_WITH_CUSTOMER = ("chat_messages", "customer_notes")


def erase_customer(conn, customer_id):
    counts = {}
    with conn:
        for table in TABLES_WITH_CUSTOMER:
            counts[table] = conn.execute(f"delete from {table} where customer_id = ?", (customer_id,)).rowcount
        counts["usage_events"] = conn.execute("update usage_events set customer_id = null where customer_id = ?", (customer_id,)).rowcount
        counts["customers"] = conn.execute("delete from customers where customer_id = ?", (customer_id,)).rowcount
    return counts


def find_residue(conn, needles):
    found = {}
    tables = [r[0] for r in conn.execute("select name from sqlite_master where type = 'table'")]
    for table in tables:
        cols = [r[1] for r in conn.execute(f"pragma table_info({table})") if r[2].upper() in ("TEXT", "")]
        for col in cols:
            for needle in needles:
                n = conn.execute(f"select count(*) from {table} where {col} like ?", (f"%{needle}%",)).fetchone()[0]
                if n:
                    found[(table, col)] = found.get((table, col), 0) + n
    return found
