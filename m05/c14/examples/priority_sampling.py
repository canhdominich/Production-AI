from _kit import day_log, unit_hash

BASE_RATE = 0.02


def choose(rows):
    chosen, probs = [], []
    for r in rows:
        if r["thumbs_down"] or unit_hash(r["id"]) < BASE_RATE:
            chosen.append(r)
            probs.append(1.0 if r["thumbs_down"] else BASE_RATE)
    return chosen, probs


def weighted_rate(chosen, probs):
    return sum(r["good"] / p for r, p in zip(chosen, probs)) / sum(1 / p for p in probs)


naive, weighted, truth, added, sizes = [], [], [], [], []
for day in range(14):
    rows = day_log(day)
    chosen, probs = choose(rows)
    naive.append(sum(r["good"] for r in chosen) / len(chosen))
    weighted.append(weighted_rate(chosen, probs))
    truth.append(sum(r["good"] for r in rows) / len(rows))
    sizes.append(len(chosen))
    added.append(sum(1 for r in chosen if r["thumbs_down"] and unit_hash(r["id"]) >= BASE_RATE))

mean = lambda xs: sum(xs) / len(xs)
print(f"base rate {BASE_RATE:.0%} plus every thumbs-down, 14 simulated days of 2000 requests")
print(f"samples per day: {mean(sizes):.0f}, of which {mean(added):.0f} came only from thumbs-down")
print(f"naive pass rate of the sample: {mean(naive):.3f}")
print(f"weighted by 1 / inclusion probability: {mean(weighted):.3f}")
print(f"true pass rate of all requests: {mean(truth):.3f}")
