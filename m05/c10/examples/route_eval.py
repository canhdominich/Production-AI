import csv
import json
import re
import unicodedata

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from _kit import HERE, PriceTable
from route_collect import CACHE, MESSAGES, pick_tasks

prices = PriceTable()


def normalize(text):
    s = unicodedata.normalize("NFD", text)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "d").lower()
    return re.sub(r"at\d{6}", "ordid", s)


with open(MESSAGES.resolve(), encoding="utf-8", newline="") as f:
    train = [r for r in csv.DictReader(f) if r["split"] == "train"]
vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
clf = LogisticRegression(C=10, max_iter=1000).fit(vec.fit_transform([normalize(r["text"]) for r in train]), [r["intent"] for r in train])

cache = json.loads(CACHE.read_text(encoding="utf-8"))
tasks = []
for t in pick_tasks():
    probs = clf.predict_proba(vec.transform([normalize(t["text"])]))[0]
    fast, deep = cache[f"{t['message_id']}:fast"], cache[f"{t['message_id']}:deep"]
    tasks.append(dict(
        truth=t["intent"], lr=clf.classes_[probs.argmax()], conf=float(probs.max()),
        fast=fast["pred"], deep=deep["pred"],
        fast_cost=prices.cost("fake-small", fast["in_tokens"], fast["out_tokens"]),
        deep_cost=prices.cost("fake-large", deep["in_tokens"], deep["out_tokens"])))


def score(decide):
    ok, cost, calls = 0, 0.0, 0
    for t in tasks:
        answer, spent, used_deep = decide(t)
        ok += answer == t["truth"]
        cost += spent
        calls += used_deep
    return ok / len(tasks), cost / len(tasks) * 1000, calls / len(tasks)


def all_fast(t):
    return t["fast"], t["fast_cost"], False


def all_deep(t):
    return t["deep"], t["deep_cost"], True


def gatekeeper(tau):
    return lambda t: (t["lr"], 0.0, False) if t["conf"] >= tau else (t["deep"], t["deep_cost"], True)


def agree(t):
    if t["fast"] == t["lr"]:
        return t["fast"], t["fast_cost"], False
    return t["deep"], t["fast_cost"] + t["deep_cost"], True


def oracle(t):
    if t["fast"] == t["truth"]:
        return t["fast"], t["fast_cost"], False
    return t["deep"], t["deep_cost"], True


print(f"{len(tasks)} test messages, six intents, same prompt for every policy")
print(f"{'policy':34}{'accuracy':>9}{'USD per 1000':>14}{'deep share':>12}")
rows = [("always fast (no thinking)", all_fast), ("always deep (thinking)", all_deep)]
rows += [(f"gatekeeper confidence >= {tau}", gatekeeper(tau)) for tau in (0.3, 0.4, 0.5, 0.6)]
rows += [("cascade: deep when fast and LR differ", agree), ("oracle (cannot be built)", oracle)]
for name, decide in rows:
    acc, cost, deep = score(decide)
    print(f"{name:34}{acc:9.3f}{cost:14.3f}{deep:11.0%}")


def wilson(k, n, z=1.96):
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
    return centre - half, centre + half


print("\n95% interval of accuracy on these 30 messages (Wilson)")
for name, key in (("always fast", "fast"), ("always deep", "deep"), ("LR alone", "lr")):
    k = sum(t[key] == t["truth"] for t in tasks)
    lo, hi = wilson(k, len(tasks))
    print(f"  {name:12} {k}/{len(tasks)} correct, {lo:.2f} to {hi:.2f}")
with open(MESSAGES.resolve(), encoding="utf-8", newline="") as f:
    test = [r for r in csv.DictReader(f) if r["split"] == "test"]
full = sum(clf.predict(vec.transform([normalize(r["text"])]))[0] == r["intent"] for r in test)
print(f"LR on all {len(test)} test messages: {full / len(test):.3f}, so these 30 are an easier slice than the full set")
mean_fast = sum(cache[f"{t['message_id']}:fast"]["out_tokens"] for t in pick_tasks()) / len(tasks)
mean_deep = sum(cache[f"{t['message_id']}:deep"]["out_tokens"] for t in pick_tasks()) / len(tasks)
print(f"output tokens per answer: fast {mean_fast:.1f}, deep {mean_deep:.1f}")
invalid = [t for t in tasks if t["deep"] == "invalid"]
print(f"deep answers cut off before a label (800-token cap): {len(invalid)} of {len(tasks)}, still billed ${sum(t['deep_cost'] for t in invalid) / len(tasks) * 1000:.3f} per 1000")
