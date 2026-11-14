import hashlib
import hmac
from dataclasses import dataclass

import jwt

from .base import TenantRegistry

ISSUER, AUDIENCE = "anhti-platform", "anhti-api"
USAGE_READERS = {"branch_manager"}


class AuthError(Exception):
    status = 401


class Forbidden(Exception):
    status = 403


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    user_id: str
    role: str
    kind: str


def issue_token(secret, tenant_id, user_id, role, now, ttl=900):
    claims = {"iss": ISSUER, "aud": AUDIENCE, "sub": user_id, "tid": tenant_id, "role": role, "iat": int(now), "exp": int(now) + ttl}
    return jwt.encode(claims, secret, algorithm="HS256")


def verify_token(secret, token, now):
    try:
        claims = jwt.decode(token, secret, algorithms=["HS256"], audience=AUDIENCE, issuer=ISSUER,
                            options={"verify_exp": False, "require": ["exp", "sub", "tid", "role"]})
    except jwt.PyJWTError as e:
        raise AuthError(f"invalid token: {type(e).__name__}") from None
    if claims["exp"] <= now:
        raise AuthError("token expired")
    return Principal(claims["tid"], claims["sub"], claims["role"], "user")


def hash_api_key(key, pepper):
    return hmac.new(pepper.encode(), key.encode(), hashlib.sha256).hexdigest()


class ApiKeyStore:
    def __init__(self, registry, pepper):
        self.pepper = pepper
        self._hashes = {hash_api_key(t.api_key, pepper): t.tenant_id for t in registry.all()}

    def verify(self, presented):
        digest = hash_api_key(presented or "", self.pepper)
        for stored, tenant_id in self._hashes.items():
            if hmac.compare_digest(stored, digest):
                return Principal(tenant_id, f"{tenant_id}:integration", "integration", "api_key")
        raise AuthError("unknown api key")


def authorize_feature(registry, principal, feature):
    tenant = registry.get(principal.tenant_id)
    try:
        registry.check_feature(tenant, feature, principal.role)
    except Exception as e:
        raise Forbidden(str(e)) from None
    return tenant


def authorize_usage_read(principal):
    if principal.role not in USAGE_READERS:
        raise Forbidden("role may not read usage")


def known_user(registry, principal):
    if principal.kind != "user":
        return principal
    tenant = registry.get(principal.tenant_id)
    for u in tenant.users:
        if u["user_id"] == principal.user_id and u["role"] == principal.role:
            return principal
    raise AuthError("user is not part of this tenant")
