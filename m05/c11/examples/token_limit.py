import redis
from _sec import redis_server
from workload import generate

TENANT = "br-ben-song"
RPM = 30
TPM = 12_000

pool = [q for q in generate(40000, seed=42) if q.tenant_id == TENANT]
cost = {q.request_id: q.prompt_tokens + q.output_tokens for q in pool}
normal = pool[:600]
heavy = sorted(pool, key=lambda q: -cost[q.request_id])[:600]
print("Ben Song requests in the pool:", len(pool))
print("tokens per request, normal traffic: median", sorted(cost[q.request_id] for q in normal)[300])
print("tokens per request, heavy requests: median", sorted(cost[q.request_id] for q in heavy)[300])


def replay(r, reqs, label):
    r.flushall()
    rp = tp = rt = tt = 0
    for i, q in enumerate(reqs):
        c = cost[q.request_id]
        minute = i // 40
        if r.incr(f"rl:req:{minute}") <= RPM:
            rp += 1
            rt += c
        if int(r.get(f"rl:tok:{minute}") or 0) + c <= TPM:
            r.incrby(f"rl:tok:{minute}", c)
            tp += 1
            tt += c
    print(f"{label:15} {RPM} per minute limit: {rp:3} passed, {rt:>8,} tokens | {TPM:,} tokens per minute limit: {tp:3} passed, {tt:>8,} tokens")


with redis_server() as port:
    r = redis.Redis(port=port, protocol=2)
    print("a loop sends 40 requests per minute for 15 minutes")
    replay(r, normal, "normal traffic")
    replay(r, heavy, "heavy requests")
