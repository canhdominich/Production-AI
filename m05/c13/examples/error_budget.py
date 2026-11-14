import _kit
from reliability import budget_status, downtime_minutes, error_budget

PER_DAY = 12000
MONTH = PER_DAY * 30
print(f"Giao Hang Anh Ti serves about {PER_DAY:,} requests per day, {MONTH:,} in 30 days")
print(f"{'SLO':>7} {'bad requests allowed':>21} {'minutes of full outage':>23}")
for slo in (0.99, 0.995, 0.999, 0.9995):
    print(f"{slo:>7.2%} {error_budget(slo, MONTH):>21,} {downtime_minutes(slo):>23.1f}")

incidents = [(3, "provider A rate-limit storm, no backoff", 350), (9, "provider A outage 35 min, no fallback", 35 * PER_DAY // 1440),
             (17, "prompt release cuts answers short", 1100), (24, "provider A slow for 2 hours", 600)]
SLO = 0.995
bad = 0
print(f"\nmonthly budget at SLO {SLO:.1%}: {error_budget(SLO, MONTH):,} bad requests")
print(f"{'day':>4} {'bad':>6} {'used':>7} {'remaining':>10}  incident")
for day, what, n in incidents:
    bad += n
    s = budget_status(SLO, MONTH, bad)
    print(f"{day:>4} {n:>6,} {s['burned']:>7.0%} {s['remaining']:>10,}  {what}")
final = budget_status(SLO, MONTH, bad)
print(f"\nend of month: {final['bad']:,} bad of {final['allowed']:,} allowed, budget {'exhausted' if final['remaining'] < 0 else 'left'}")
