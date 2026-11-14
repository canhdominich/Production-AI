import base64
import json
import jwt
from _sec import AuthError, issue_token, verify_token

NOW = 1_800_000_000
KEYRING = {"k1": "demo-signing-secret-k1-change-me-0123456789"}


def b64(d):
    return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()


def try_verify(label, token, now=NOW + 60):
    try:
        c = verify_token(KEYRING, token, now)
        print(f"{label:34} accepted  tenant={c['tenant']} role={c['role']}")
    except AuthError as e:
        print(f"{label:34} rejected  {e}")


good = issue_token(KEYRING, "k1", "br-cau-go", "cg-02", "branch_lead", NOW)
try_verify("valid token", good)

head, body, sig = good.split(".")
claims = json.loads(base64.urlsafe_b64decode(body + "=="))
claims["tenant"] = "br-dau-pho"
try_verify("tenant edited, old signature", f"{head}.{b64(claims)}.{sig}")

none_token = f"{b64({'alg': 'none', 'typ': 'JWT', 'kid': 'k1'})}.{b64(claims)}."
try_verify("alg none", none_token)

try_verify("expired (16 minutes later)", good, now=NOW + 960)

wrong_aud = jwt.encode({**claims, "aud": "other-service", "iss": "anhti-api", "exp": NOW + 900}, KEYRING["k1"], algorithm="HS256", headers={"kid": "k1"})
try_verify("wrong audience", wrong_aud)

no_tenant = {k: v for k, v in claims.items() if k != "tenant"}
no_tenant.update(iss="anhti-api", aud="anhti-ai", exp=NOW + 900)
try_verify("signed but no tenant claim", jwt.encode(no_tenant, KEYRING["k1"], algorithm="HS256", headers={"kid": "k1"}))

try_verify("unknown kid", jwt.encode({**claims}, "x" * 40, algorithm="HS256", headers={"kid": "k9"}))

print("jwt library:", jwt.__version__)
