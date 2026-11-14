import json

from _bench import DATA

SLO_TTFT, SLO_TPOT = 3.0, 0.25
runs = json.loads((DATA / "ollama_runs.json").read_text())
print(f"SLO: ttft <= {SLO_TTFT:.1f} s and tpot <= {SLO_TPOT*1000:.0f} ms")
print("conc  ok/n   ok%    throughput   goodput")
for c, run in runs.items():
    recs, wall = run["recs"], run["wall"]
    ok = [r for r in recs if r["ttft"] <= SLO_TTFT and r["tpot"] <= SLO_TPOT]
    tok = sum(r["n_out"] for r in recs)
    good = sum(r["n_out"] for r in ok)
    print(f"{c:>4} {len(ok):>3}/{len(recs):<3} {100*len(ok)/len(recs):5.1f}%  {tok/wall:6.2f} t/s  {good/wall:6.2f} t/s")
