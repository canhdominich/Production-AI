import csv
import random
from collections import Counter, defaultdict
from pathlib import Path

rows = list(csv.DictReader(open(Path(__file__).resolve().parents[3] / "m02" / "data" / "messages.csv", encoding="utf-8")))
text = ["<s>"]
for r in rows:
    text += r["text"].lower().split() + ["</s>"]
vocab = sorted(set(text))


def fit(order):
    t = defaultdict(Counter)
    for i in range(order, len(text)):
        t[tuple(text[i - order:i])][text[i]] += 1
    return t


big, small = fit(2), fit(1)


def dist(model, order, ctx):
    c = model.get(tuple(ctx[-order:]))
    if not c:
        return {w: 1 / len(vocab) for w in vocab}
    n = sum(c.values()) + 0.5
    d = {w: 0.5 / len(vocab) / n for w in vocab}
    for w, k in c.items():
        d[w] += k / n
    return d


def sample(d, rnd):
    x, acc = rnd.random(), 0.0
    for w, p in d.items():
        acc += p
        if x <= acc:
            return w
    return w


def speculative(ctx, gamma, rnd, stats):
    drafts, ctx2 = [], list(ctx)
    qs = []
    for _ in range(gamma):
        q = dist(small, 1, ctx2)
        w = sample(q, rnd)
        drafts.append(w)
        qs.append(q)
        ctx2.append(w)
    stats["target_calls"] += 1
    out = []
    for w, q in zip(drafts, qs):
        p = dist(big, 2, list(ctx) + out)
        if rnd.random() < min(1.0, p[w] / q[w]):
            out.append(w)
            stats["accepted"] += 1
        else:
            stats["rejected"] += 1
            r = {x: max(0.0, p[x] - q[x]) for x in vocab}
            z = sum(r.values())
            out.append(sample({x: v / z for x, v in r.items()}, rnd))
            return out
    out.append(sample(dist(big, 2, list(ctx) + out), rnd))
    return out


rnd = random.Random(7)
ctx = max((k for k, v in big.items() if len(v) >= 4), key=lambda k: sum(big[k].values()))
ctx = list(ctx)
print(f"context {ctx}, vocabulary {len(vocab)} words, target = bigram-context model (order 2), draft = unigram-context model (order 1)")
exact = Counter(sample(dist(big, 2, ctx), rnd) for _ in range(20000))
spec = Counter(speculative(ctx, 4, rnd, Counter())[0] for _ in range(20000))
top = [w for w, _ in exact.most_common(5)]
print("first token frequency, target alone vs speculative (20000 draws each):")
for w in top:
    print(f"  {w:<8} {exact[w]/20000:.3f}   {spec[w]/20000:.3f}")
print("gamma  alpha  tokens per call  formula  speedup at draft cost 10%  speedup at draft cost 60%")
for gamma in (1, 2, 4, 8):
    stats, produced, calls = Counter(), 0, 0
    for _ in range(3000):
        c = ["<s>"] + rnd.choice(rows)["text"].lower().split()[:2]
        produced += len(speculative(c, gamma, rnd, stats))
    calls = stats["target_calls"]
    alpha = stats["accepted"] / (stats["accepted"] + stats["rejected"])
    formula = (1 - alpha ** (gamma + 1)) / (1 - alpha)
    tpc = produced / calls
    print(f"{gamma:>5}  {alpha:5.2f}  {tpc:15.2f}  {formula:7.2f}  {tpc / (1 + 0.1 * gamma):21.2f}x  {tpc / (1 + 0.6 * gamma):24.2f}x")
