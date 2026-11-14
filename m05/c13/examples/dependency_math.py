import _kit
from reliability import downtime_minutes

chain = [("Caddy", 0.9995), ("API", 0.999), ("Gateway", 0.9995), ("PostgreSQL", 0.9995)]
A, B = 0.995, 0.995


def series(items):
    p = 1.0
    for _, a in items:
        p *= a
    return p


def both_down(qa, qb, correlated):
    return correlated * min(qa, qb) + (1 - correlated) * qa * qb


base = series(chain)
print(f"our own parts in series: {base:.4%}  ({downtime_minutes(base):.0f} min/month)")
print(f"{'model provider setup':<44} {'provider':>9} {'whole service':>14} {'min/month down':>15}")
rows = [("single provider A (99.5%)", A)]
for corr in (0.0, 0.3, 0.6):
    rows.append((f"A + fallback B, {corr:.0%} of failures shared", 1 - both_down(1 - A, 1 - B, corr)))
for label, p in rows:
    total = base * p
    print(f"{label:<44} {p:>9.4%} {total:>14.4%} {downtime_minutes(total):>15.0f}")
