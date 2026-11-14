import random

from prometheus_client import generate_latest

from _kit import day_log
from _metrics import COST, EVAL, FINISH, LATENCY, PSI, REQUESTS, registry

rnd = random.Random(3)
for r in day_log(0, n=300):
    status = "error" if rnd.random() < 0.01 else "ok"
    REQUESTS.labels(r["feature"], status).inc()
    LATENCY.labels(r["feature"]).observe(rnd.lognormvariate(0.3, 0.7))
    FINISH.labels(r["feature"], "length" if rnd.random() < 0.03 else "stop").inc()
    COST.labels(r["tenant"]).inc(0.0004)
    if rnd.random() < 0.1:
        EVAL.labels(r["feature"], "pass" if r["good"] else "fail").inc()
PSI.labels("chat").set(0.021)
PSI.labels("knowledge_assistant").set(0.034)

lines = generate_latest(registry).decode().splitlines()
keep = [x for x in lines if "_created" not in x and (x.startswith(("llm_requests_total{", "llm_eval_samples_total{", "llm_input_psi{", "# TYPE")) or 'le="5.0"' in x and "chat" in x)]
print("\n".join(keep))
print(f"... {len(lines)} lines in total, series per metric are bounded by feature, status, reason, tenant")
