import time

from app import db, settings
from app.gateway import GatewayError, GatewayRequest, make_gateway


def main():
    gateway = make_gateway()
    r = db.redis_client()
    print("worker started", flush=True)
    while True:
        r.set(settings.HEARTBEAT, str(int(time.time())), ex=15)
        item = r.brpop(settings.QUEUE, timeout=2)
        if not item:
            continue
        job_id = item[1]
        with db.connect() as conn:
            row = conn.execute(f"update {settings.SCHEMA}.jobs set status = 'running' where job_id = %s returning tenant_id, week", (job_id,)).fetchone()
            if not row:
                continue
            req = GatewayRequest(row[0], "weekly_report_agent", [{"role": "user", "content": f"Weekly report for {row[0]}, week {row[1]}"}], tier="large", role="branch_manager", output_tokens=120)
            try:
                resp = gateway.handle(req)
            except GatewayError as e:
                conn.execute(f"update {settings.SCHEMA}.jobs set status = 'failed', result = %s, finished_at = now() where job_id = %s", (f"{type(e).__name__}: {e}", job_id))
                print("job failed", job_id, type(e).__name__, flush=True)
                continue
            db.save_usage(conn, resp.record)
            conn.execute(f"update {settings.SCHEMA}.jobs set status = 'done', result = %s, finished_at = now() where job_id = %s", (resp.text, job_id))
        print("job done", job_id, flush=True)


if __name__ == "__main__":
    main()
