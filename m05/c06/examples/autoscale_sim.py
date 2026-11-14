import heapq
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "platform"))
from common import percentile
from gateway_core import PriceTable
from workload import generate
from _vram import CFG, GIB, activation_bytes, kv_bytes_per_token, param_count, weight_bytes

GPU_USD_PER_H = 1.80
TPOT_S, PREFILL_TOK_S, TTFT_BASE_S = 0.03, 4000.0, 0.3
COLD_S = 75.0
TICK_S, CHECK_S = 1, 15
SCALE_UP_AT = 0.7


def slots_per_replica(m, bits, ctx, card_gib, util=0.9, overhead_gib=1.0, batched=4096):
    free = card_gib * GIB * util - weight_bytes(param_count(m), bits) - activation_bytes(m, batched) - overhead_gib * GIB
    return max(0, int(free // (kv_bytes_per_token(m) * ctx)))


def simulate(reqs, slots, min_rep, max_rep, idle_s, slow_s, cold_s=COLD_S):
    arrivals = [(r.arrival_s, TTFT_BASE_S + r.prompt_tokens / PREFILL_TOK_S + r.output_tokens * TPOT_S) for r in reqs]
    reps, queue, waits, gpu_s, cold_starts, nxt = [], [], [], 0.0, 0, 0
    for _ in range(min_rep):
        reps.append({"ready": 0.0, "busy": [], "idle_since": 0.0})
    for t in range(0, 86400 + 3600, TICK_S):
        while nxt < len(arrivals) and arrivals[nxt][0] <= t:
            queue.append(arrivals[nxt])
            nxt += 1
        for r in reps:
            while r["busy"] and r["busy"][0] <= t:
                heapq.heappop(r["busy"])
            if not r["busy"] and r["idle_since"] is None:
                r["idle_since"] = t
        for r in reps:
            if r["ready"] <= t:
                while queue and len(r["busy"]) < slots:
                    arr, svc = queue.pop(0)
                    waits.append(t - arr)
                    heapq.heappush(r["busy"], t + svc)
                    r["idle_since"] = None
        if t % CHECK_S == 0:
            ready = [r for r in reps if r["ready"] <= t]
            load = (sum(len(r["busy"]) for r in ready) + len(queue)) / max(1, len(ready) * slots)
            starting = len(reps) - len(ready)
            if len(reps) < max_rep and starting == 0 and (load > SCALE_UP_AT or (not reps and queue)):
                reps.append({"ready": t + cold_s, "busy": [], "idle_since": None})
                cold_starts += 1
            for r in list(reps):
                if r["ready"] <= t and not r["busy"] and not queue and r["idle_since"] is not None and t - r["idle_since"] >= idle_s and len(reps) > min_rep:
                    reps.remove(r)
        gpu_s += len(reps) * TICK_S
        if nxt >= len(arrivals) and not queue and all(not r["busy"] for r in reps) and t > 86400:
            break
    return {"gpu_h": gpu_s / 3600, "cost": gpu_s / 3600 * GPU_USD_PER_H, "p50": percentile(waits, 50), "p95": percentile(waits, 95), "p99": percentile(waits, 99),
            "slow": sum(1 for w in waits if w > slow_s), "n": len(waits), "cold_starts": cold_starts}


def report(title, reqs, slots, slow_s, policies):
    print(f"{title}: {len(reqs)} requests, wait above {slow_s} s counts as slow")
    print("policy                            GPU_h   USD  p95_s  p99_s  slow  cold_starts")
    for label, lo, hi, idle in policies:
        s = simulate(reqs, slots, lo, hi, idle, slow_s)
        print(f"{label:<32} {s['gpu_h']:>6.1f} {s['cost']:>5.0f} {s['p95']:>6.1f} {s['p99']:>6.1f} {s['slow']:>5} {s['cold_starts']:>8}")
    print()


if __name__ == "__main__":
    m = CFG["models"]["qwen3-8b"]
    slots = slots_per_replica(m, CFG["quant_bits_per_weight"]["bf16"], 4096, 24)
    print(f"qwen3-8b bf16 on a 24 GiB card holds {slots} sequences per replica; cold start {COLD_S:.0f} s; GPU {GPU_USD_PER_H} USD per hour\n")
    report("Busy chat service", generate(40000), slots, 5, [("always 1 replica", 1, 1, 0), ("always 2 replicas", 2, 2, 0),
           ("min 1, max 3, idle 300 s", 1, 3, 300), ("scale to zero, max 3, idle 300 s", 0, 3, 300)])
    report("Quiet chat service", generate(1500, mix={"chat": 1.0}), slots, 5, [("always 1 replica", 1, 1, 0),
           ("scale to zero, idle 300 s", 0, 1, 300), ("scale to zero, idle 1800 s", 0, 1, 1800)])
    report("Weekly report jobs", generate(600, mix={"weekly_report_agent": 1.0}), slots, 120, [("always 1 replica", 1, 1, 0),
           ("scale to zero, idle 300 s", 0, 1, 300)])

    busy = generate(40000)
    table = PriceTable()
    as_medium = sum(table.cost("fake-medium", r.prompt_tokens, r.output_tokens) for r in busy)
    as_mixed = sum(table.cost(r.model, r.prompt_tokens, r.output_tokens) for r in busy)
    print(f"Same 40000 requests priced through the API table: {as_mixed:.0f} USD per day with the real tier mix, {as_medium:.0f} USD if every request used the medium tier")
