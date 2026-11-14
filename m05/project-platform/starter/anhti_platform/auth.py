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
    # TODO 1: giải mã JWT bằng HS256 (chỉ nhận thuật toán này), kiểm issuer, audience, các claim bắt buộc; hết hạn tính theo now; lỗi thì ném AuthError
    claims = jwt.decode(token, options={"verify_signature": False})
    return Principal(claims["tid"], claims["sub"], claims["role"], "user")


def hash_api_key(key, pepper):
    return hmac.new(pepper.encode(), key.encode(), hashlib.sha256).hexdigest()


class ApiKeyStore:
    def __init__(self, registry, pepper):
        self.pepper = pepper
        self._hashes = {hash_api_key(t.api_key, pepper): t.tenant_id for t in registry.all()}

    def verify(self, presented):
        # TODO 2: băm khóa nhận được rồi so với từng băm đã lưu bằng hmac.compare_digest; trả Principal kind api_key hoặc ném AuthError
        raise NotImplementedError('TODO 2')


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
    # TODO 3: token hợp lệ chưa đủ: tìm user_id trong tenant và so khớp vai trò với danh bạ, nếu không khớp thì ném AuthError
    return principal
