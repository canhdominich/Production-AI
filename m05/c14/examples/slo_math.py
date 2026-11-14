SLO, PERIOD_H, DAILY = 0.995, 30 * 24, 2000
budget = 1 - SLO
requests = DAILY * 30
print(f"SLO {SLO:.1%} over 30 days: error budget {budget:.1%} of {requests:,} requests = {requests * budget:.0f} failed requests, or {PERIOD_H * 60 * budget:.0f} minutes of total outage")
print()
print(f"{'burn rate':>10}{'budget gone in':>16}{'error ratio':>13}   how the rule uses it")
for rate, note in ((1, "slow leak, open a ticket"), (3, "ticket within a day"), (6, "page: gone in 5 days"), (14.4, "page: gone in 2 days"), (36, "page: gone in 20 hours")):
    hours = PERIOD_H / rate
    print(f"{rate:>10}{hours / 24:>13.1f} d{rate * budget:>13.1%}   {note}")
print()
print("share of the 30-day budget burned if the burn rate lasts for the whole long window")
for rate, window_h in ((14.4, 1), (6, 6), (3, 24), (1, 72)):
    print(f"burn rate {rate:>4} for {window_h:>2} h burns {rate * window_h / PERIOD_H:.1%} of the budget")
