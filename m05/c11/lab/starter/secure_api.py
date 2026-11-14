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
        # TODO 4: thêm khóa mới vào self.keys và đặt nó làm khóa ký (active); giữ khóa cũ để xác minh token cũ
        raise NotImplementedError

    def retire(self, kid):
        # TODO 4: xóa khóa cũ khỏi self.keys; nếu là khóa đang ký thì raise ValueError
        raise NotImplementedError


def issue_token(ring, tenant, user, role, now, ttl=900):
    claims = {"iss": ISSUER, "aud": AUDIENCE, "sub": user, "tenant": tenant, "role": role, "iat": int(now), "exp": int(now) + ttl}
    return jwt.encode(claims, ring.keys[ring.active], algorithm="HS256", headers={"kid": ring.active})


def verify_token(ring, token, now):
    # TODO 1: đọc kid từ header, lấy khóa trong ring (không có thì AuthError("unknown_kid")),
    # decode với algorithms=["HS256"], audience, issuer, bắt buộc các claim trong REQUIRED.
    # Tự kiểm hạn dùng bằng so sánh claims["exp"] với `now` (tắt verify_exp, verify_iat, verify_nbf của thư viện)
    # và từ chối tenant rỗng. Mọi lỗi của thư viện đổi thành AuthError.
    raise NotImplementedError


def new_api_key():
    key_id = secrets.token_hex(4)
    return key_id, f"gd_{key_id}_{secrets.token_urlsafe(32)}"


def hash_api_key(full_key):
    # TODO 2: trả về SHA-256 dạng hex của khóa đầy đủ
    raise NotImplementedError


def verify_api_key(store, presented):
    # TODO 2: tách "gd_<id>_<secret>", tìm hàng theo id, từ chối khóa đã thu hồi,
    # so sánh băm bằng hmac.compare_digest, trả về tenant hoặc None
    raise NotImplementedError


class RateLimiter:
    def __init__(self, client, limit_per_minute):
        self.r = client
        self.limit = limit_per_minute

    def allow(self, tenant, now):
        # TODO 3: dùng INCR trên khóa rl:<tenant>:<phút>, đặt EXPIRE 120 giây ở lần đầu, cho phép khi đếm <= limit
        raise NotImplementedError


TABLES_WITH_CUSTOMER = ("chat_messages", "customer_notes")


def erase_customer(conn, customer_id):
    # TODO 5: trong một giao dịch: xóa hàng của khách ở các bảng TABLES_WITH_CUSTOMER,
    # gỡ customer_id (đặt NULL) ở usage_events để giữ số liệu kế toán, xóa khách khỏi customers.
    # Trả về dict số hàng bị ảnh hưởng theo bảng.
    raise NotImplementedError


def find_residue(conn, needles):
    # TODO 6: duyệt mọi bảng và mọi cột kiểu TEXT; trả về {(bảng, cột): số hàng chứa needle} cho các nơi còn sót
    raise NotImplementedError
