import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app import db, settings
from app.gateway import GatewayError, GatewayRequest, make_gateway

app = FastAPI(title="Anh Ti AI API")
gateway = make_gateway()
redis_conn = db.redis_client()


class ChatIn(BaseModel):
    tenant_id: str
    text: str


class ReportIn(BaseModel):
    tenant_id: str
    week: str


@app.get("/health")
def health():
    return {"status": "alive"}


@app.get("/ready")
def ready():
    try:
        with db.connect() as conn:
            conn.execute("select 1")
        redis_conn.ping()
    except Exception as e:
        raise HTTPException(503, f"not ready: {type(e).__name__}")
    return {"status": "ready"}


@app.post("/chat")
def chat(body: ChatIn):
    req = GatewayRequest(body.tenant_id, "chat", [{"role": "user", "content": body.text}], tier="small", output_tokens=40)
    try:
        resp = gateway.handle(req)
    except GatewayError as e:
        raise HTTPException(e.status, str(e) or type(e).__name__)
    with db.connect() as conn:
        db.save_usage(conn, resp.record)
    return {"request_id": resp.request_id, "text": resp.text[:80], "cost_usd": round(resp.record.cost_usd, 6)}


@app.post("/reports", status_code=202)
def create_report(body: ReportIn):
    try:
        gateway.tenants.check_feature(gateway.tenants.get(body.tenant_id), "weekly_report_agent", "branch_manager")
    except GatewayError as e:
        raise HTTPException(e.status, str(e) or type(e).__name__)
    job_id = uuid.uuid4().hex[:10]
    with db.connect() as conn:
        conn.execute(f"insert into {settings.SCHEMA}.jobs (job_id, tenant_id, week) values (%s, %s, %s)", (job_id, body.tenant_id, body.week))
    redis_conn.lpush(settings.QUEUE, job_id)
    return {"job_id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    with db.connect() as conn:
        row = conn.execute(f"select job_id, status, left(coalesce(result, ''), 60) from {settings.SCHEMA}.jobs where job_id = %s", (job_id,)).fetchone()
    if not row:
        raise HTTPException(404, "unknown job")
    return {"job_id": row[0], "status": row[1], "result": row[2]}


@app.get("/stats")
def stats():
    with db.connect() as conn:
        usage = conn.execute(f"select count(*) from {settings.SCHEMA}.usage_events").fetchone()[0]
        jobs = conn.execute(f"select status, count(*) from {settings.SCHEMA}.jobs group by 1 order by 1").fetchall()
    return {"usage_events": usage, "jobs": {s: n for s, n in jobs}, "queue_length": redis_conn.llen(settings.QUEUE)}
