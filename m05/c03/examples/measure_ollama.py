import json
import statistics
import time

from _bench import DATA, one, prompts, run_concurrent
from common import percentile

LEVELS = (1, 8, 32)
ps = prompts(32)
one(ps[0], 4)
runs = {}
print("conc  n  ttft p50  ttft p95  tpot p50  tokens  wall    throughput  per-user")
for c in LEVELS:
    if c == 1:
        recs, wall = [], 0.0
        t0 = time.perf_counter()
        for p in ps[:4]:
            recs.append(one(p))
        wall = time.perf_counter() - t0
    else:
        recs, wall = run_concurrent(ps[:c])
    runs[c] = dict(wall=wall, recs=recs)
    tok = sum(r["n_out"] for r in recs)
    ttft = [r["ttft"] for r in recs]
    tpot = [r["tpot"] for r in recs if r["tpot"]]
    print(f"{c:>4} {len(recs):>3}  {statistics.median(ttft):8.2f}  {percentile(ttft, 95):8.2f}  {statistics.median(tpot)*1000:6.0f} ms  {tok:>5}  {wall:6.1f}  {tok/wall:7.2f} t/s  {statistics.median([r['n_out']/r['total'] for r in recs]):6.2f} t/s")
DATA.mkdir(exist_ok=True)
(DATA / "ollama_runs.json").write_text(json.dumps({str(k): v for k, v in runs.items()}, indent=1))
