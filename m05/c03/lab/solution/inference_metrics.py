def ttft(rec):
    return rec["token_times"][0] - rec["sent"]


def tpot(rec):
    times = rec["token_times"]
    if len(times) < 2:
        return 0.0
    return (times[-1] - times[0]) / (len(times) - 1)


def window(recs):
    start = min(r["sent"] for r in recs)
    end = max(r["token_times"][-1] for r in recs)
    return end - start


def throughput(recs):
    return sum(len(r["token_times"]) for r in recs) / window(recs)


def meets_slo(rec, slo_ttft, slo_tpot):
    return ttft(rec) <= slo_ttft and tpot(rec) <= slo_tpot


def goodput(recs, slo_ttft, slo_tpot):
    good = sum(len(r["token_times"]) for r in recs if meets_slo(r, slo_ttft, slo_tpot))
    return good / window(recs)


def max_concurrency_within_slo(curve, min_ok_fraction=0.9):
    best = 0
    for point in sorted(curve, key=lambda p: p["concurrency"]):
        if point["ok_fraction"] < min_ok_fraction:
            break
        best = point["concurrency"]
    return best
