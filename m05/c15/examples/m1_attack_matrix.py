import jwt

import _kit  # noqa: F401
from conftest import NOW, World
from anhti_platform.auth import issue_token
from conftest import settings

w = World()
secret = settings().jwt_secret
good = w.login("dp-03")
unsigned = jwt.encode({"iss": "anhti-platform", "aud": "anhti-api", "sub": "dp-03", "tid": "br-dau-pho", "role": "branch_manager",
                       "exp": int(NOW) + 900}, key=None, algorithm="none")
bearer = lambda t: {"authorization": "Bearer " + t}  # noqa: E731
probes = [
    ("manager reads own usage", "GET", "/v1/usage", good, None),
    ("no credentials", "GET", "/v1/usage", {}, None),
    ("unsigned token (alg none)", "GET", "/v1/usage", bearer(unsigned), None),
    ("token signed with another key", "GET", "/v1/usage", bearer(issue_token("x" * 40, "br-dau-pho", "dp-03", "branch_manager", NOW)), None),
    ("expired token", "GET", "/v1/usage", bearer(issue_token(secret, "br-dau-pho", "dp-03", "branch_manager", NOW - 2000)), None),
    ("promoted role inside the token", "GET", "/v1/usage", bearer(issue_token(secret, "br-dau-pho", "dp-01", "branch_manager", NOW)), None),
    ("manager reads another tenant", "GET", "/v1/usage/br-khu-cong-nghiep", good, None),
    ("manager reads a tenant that does not exist", "GET", "/v1/usage/br-nowhere", good, None),
    ("agent reads usage", "GET", "/v1/usage", w.login("dp-01"), None),
    ("agent asks knowledge assistant", "POST", "/v1/chat", w.login("dp-01"), {"message": "hi", "feature": "knowledge_assistant"}),
    ("body names another tenant", "POST", "/v1/chat", w.login("dp-01"), {"message": "hi", "tenant_id": "br-cau-go"}),
    ("api key of Cau Go", "POST", "/v1/chat", {"x-api-key": "demo-key-cau-go"}, {"message": "hi"}),
    ("api key with a typo", "POST", "/v1/chat", {"x-api-key": "demo-key-cau-g0"}, {"message": "hi"}),
]
print(f"{'probe':46}{'status':>7}  error code")
for name, method, path, headers, body in probes:
    r = w.http.request(method, path, headers=headers, json=body)
    code = r.json().get("error", {}).get("code", "") if r.status_code >= 400 and r.headers["content-type"].startswith("application/json") else ""
    print(f"{name:46}{r.status_code:>7}  {code}")
