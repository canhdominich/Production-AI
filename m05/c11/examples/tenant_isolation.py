from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from _sec import AuthError, issue_token, load_tenants, verify_token

NOW = 1_800_000_000
KEYRING = {"k1": "demo-signing-secret-k1-change-me-0123456789"}
ROLES, TENANTS = load_tenants()
HISTORY = {"br-cau-go": ["Cau Go: customer asks AT1001 address"], "br-ben-song": ["Ben Song: customer asks AT2002 refund"]}

app = FastAPI()


def principal(authorization):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing token")
    try:
        return verify_token(KEYRING, authorization[7:], NOW + 30)
    except AuthError as e:
        raise HTTPException(401, str(e))


class Body(BaseModel):
    tenant_id: str
    feature: str = "chat"


@app.post("/v1/history-trusting-body")
def history_bad(body: Body, authorization: str = Header(None)):
    principal(authorization)
    return HISTORY[body.tenant_id]


@app.post("/v1/history")
def history_good(authorization: str = Header(None)):
    return HISTORY[principal(authorization)["tenant"]]


@app.post("/v1/ask/{feature}")
def ask(feature: str, authorization: str = Header(None)):
    p = principal(authorization)
    if feature not in TENANTS[p["tenant"]]["allowed_features"]:
        raise HTTPException(403, "tenant does not have " + feature)
    if feature not in ROLES[p["role"]]["features"]:
        raise HTTPException(403, "role " + p["role"] + " cannot use " + feature)
    return {"ok": True}


c = TestClient(app)
tok = lambda tenant, uid, role: {"Authorization": "Bearer " + issue_token(KEYRING, "k1", tenant, uid, role, NOW)}
bs = tok("br-ben-song", "bs-01", "cskh_agent")
print("no token                  :", c.post("/v1/history").status_code)
r = c.post("/v1/history-trusting-body", json={"tenant_id": "br-cau-go"}, headers=bs)
print("body trusted, Ben Song asks for Cau Go:", r.status_code, r.json())
r = c.post("/v1/history-trusting-body", json={"tenant_id": "br-ben-song"}, headers=bs)
print("body trusted, honest request          :", r.status_code, r.json())
r = c.post("/v1/history", json={"tenant_id": "br-cau-go"}, headers=bs)
print("tenant from token, same attack        :", r.status_code, r.json())
print("--- roles and plans")
print("cskh_agent  chat                 :", c.post("/v1/ask/chat", headers=bs).status_code)
print("cskh_agent  weekly_report_agent  :", c.post("/v1/ask/weekly_report_agent", headers=bs).status_code, c.post("/v1/ask/weekly_report_agent", headers=bs).json()["detail"])
mg = tok("br-ben-song", "bs-02", "branch_lead")
print("Ben Song plan, lead, weekly report:", c.post("/v1/ask/weekly_report_agent", headers=mg).status_code, c.post("/v1/ask/weekly_report_agent", headers=mg).json()["detail"])
mc = tok("br-cau-go", "cg-03", "branch_manager")
print("Cau Go manager, weekly report     :", c.post("/v1/ask/weekly_report_agent", headers=mc).status_code)
cg_agent = tok("br-cau-go", "cg-01", "cskh_agent")
r = c.post("/v1/ask/weekly_report_agent", headers=cg_agent)
print("Cau Go plan ok, role cskh_agent   :", r.status_code, r.json()["detail"])
