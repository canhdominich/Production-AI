import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "support_messages.jsonl"


def load():
    return [json.loads(line) for line in DATA.read_text(encoding="utf-8").splitlines()]


def secrets_of(records, kinds=("phone", "address")):
    return [s["text"] for r in records for s in r["pii"] if s["kind"] in kinds]


def covered(spans, gold):
    return any(a <= gold["start"] and b >= gold["end"] for a, b, *_ in spans)


def score(records, finder, kind):
    tp = fn = fp = 0
    for r in records:
        got = [s for s in finder(r["text"]) if kind in (s[2] if len(s) > 2 else kind)]
        gold = [s for s in r["pii"] if s["kind"] == kind]
        for g in gold:
            if covered(got, g):
                tp += 1
            else:
                fn += 1
        for a, b, *_ in got:
            if not any(g["start"] < b and a < g["end"] for g in gold):
                fp += 1
    return tp, fp, fn
