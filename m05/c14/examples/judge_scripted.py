import json
import random

from _kit import FakeLLM, JUDGE_TNR as TNR, JUDGE_TPR as TPR

RUBRIC = "Answer PASS only if the reply is grounded in the cited policy and answers the question. Reply as JSON: {\"verdict\": \"pass|fail\", \"reason\": \"...\"}."


def make_script(truths, seed, broken_at=()):
    rnd = random.Random(seed)
    script = []
    for i, truth in enumerate(truths):
        says_pass = rnd.random() < (TPR if truth else 1 - TNR)
        if i in broken_at:
            script.append("Pass, the answer looks fine to me.")
        else:
            script.append(json.dumps({"verdict": "pass" if says_pass else "fail", "reason": "scripted"}))
    return script


def judge_all(items, truths, seed, broken_at=()):
    llm = FakeLLM(make_script(truths, seed, broken_at))
    out = []
    for item in items:
        reply = llm.chat([{"role": "system", "content": RUBRIC}, {"role": "user", "content": item}]).text
        try:
            out.append(json.loads(reply)["verdict"] == "pass")
        except (ValueError, KeyError):
            out.append(None)
    return out


def correct(measured, tpr, tnr):
    return min(1.0, max(0.0, (measured + tnr - 1) / (tpr + tnr - 1)))


rnd = random.Random(5)
GOLD = 200
gold_truth = [rnd.random() < 0.70 for _ in range(GOLD)]
gold_verdict = judge_all([f"gold-{i}" for i in range(GOLD)], gold_truth, seed=11, broken_at={7, 40, 93})
usable = [(t, v) for t, v in zip(gold_truth, gold_verdict) if v is not None]
tp = sum(1 for t, v in usable if t and v)
tn = sum(1 for t, v in usable if not t and not v)
pos = sum(1 for t, _ in usable if t)
neg = len(usable) - pos
tpr, tnr = tp / pos, tn / neg
print(f"gold set: {GOLD} answers with human labels, {GOLD - len(usable)} judge replies could not be parsed")
print(f"judge agrees with humans on {(tp + tn) / len(usable):.1%}; TPR {tpr:.3f}, TNR {tnr:.3f}")

measured, corrected, truth = [], [], []
for day in range(14):
    day_truth = [rnd.random() < 0.90 for _ in range(400)]
    verdicts = [v for v in judge_all([f"prod-{day}-{i}" for i in range(400)], day_truth, seed=100 + day) if v is not None]
    m = sum(verdicts) / len(verdicts)
    measured.append(m)
    corrected.append(correct(m, tpr, tnr))
    truth.append(sum(day_truth) / 400)
mean = lambda xs: sum(xs) / len(xs)
print(f"\n14 production days, 400 sampled answers each, true pass rate {mean(truth):.3f}")
print(f"mean measured by the judge: {mean(measured):.3f}")
print(f"mean corrected with gold-set TPR and TNR: {mean(corrected):.3f}")
print(f"day 1: measured {measured[0]:.3f}, corrected {corrected[0]:.3f}, true {truth[0]:.3f}")
