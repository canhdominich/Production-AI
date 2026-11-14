import hashlib
import hmac
import json
import secrets
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import jwt

M05 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(M05 / "platform"))

ISSUER = "anhti-api"
AUDIENCE = "anhti-ai"
PORT_REDIS = 5711
PG = dict(host="localhost", port=55432, user="anhti", password="anhti", dbname="anhti")
SCHEMA = "m05_c11"


def load_tenants():
    data = json.loads((M05 / "data" / "tenants.json").read_text(encoding="utf-8"))
    return data["roles"], {t["tenant_id"]: t for t in data["tenants"]}


class AuthError(Exception):
    pass


def issue_token(keyring, active_kid, tenant_id, user_id, role, now, ttl=900):
    claims = {"iss": ISSUER, "aud": AUDIENCE, "sub": user_id, "tenant": tenant_id, "role": role, "iat": int(now), "exp": int(now) + ttl}
    return jwt.encode(claims, keyring[active_kid], algorithm="HS256", headers={"kid": active_kid})


def verify_token(keyring, token, now):
    try:
        kid = jwt.get_unverified_header(token).get("kid")
        key = keyring.get(kid)
        if key is None:
            raise AuthError("unknown_kid")
        claims = jwt.decode(token, key, algorithms=["HS256"], audience=AUDIENCE, issuer=ISSUER,
                            options={"require": ["exp", "iat", "sub", "tenant", "role"], "verify_exp": False, "verify_iat": False, "verify_nbf": False})
    except jwt.InvalidTokenError as e:
        raise AuthError(type(e).__name__) from None
    if claims["exp"] <= now:
        raise AuthError("expired")
    return claims


def new_api_key():
    key_id = secrets.token_hex(4)
    secret = secrets.token_urlsafe(32)
    return key_id, f"gd_{key_id}_{secret}"


def hash_key(full_key):
    return hashlib.sha256(full_key.encode()).hexdigest()


def check_key(store, presented):
    parts = presented.split("_", 2)
    if len(parts) != 3 or parts[0] != "gd":
        return None
    row = store.get(parts[1])
    if row and hmac.compare_digest(row["hash"], hash_key(presented)) and not row.get("revoked"):
        return row["tenant"]
    return None


@contextmanager
def redis_server(port=PORT_REDIS):
    proc = subprocess.Popen(["redis-server", "--port", str(port), "--save", "", "--appendonly", "no", "--bind", "127.0.0.1"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        import redis
        r = redis.Redis(port=port, protocol=2)
        for _ in range(50):
            try:
                r.ping()
                break
            except redis.ConnectionError:
                time.sleep(0.1)
        yield port
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def pg():
    import psycopg
    conn = psycopg.connect(**PG, autocommit=True)
    conn.execute(f"create schema if not exists {SCHEMA}")
    conn.execute(f"set search_path to {SCHEMA}, public")
    return conn
