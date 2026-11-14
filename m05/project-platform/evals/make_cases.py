import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[2] / "m02" / "data" / "messages.csv"
PER_INTENT = 15

rows = sorted(csv.DictReader(SRC.open(encoding="utf-8")), key=lambda r: r["message_id"])
picked, count = [], {}
for r in rows:
    n = count.get(r["intent"], 0)
    if n < PER_INTENT:
        count[r["intent"]] = n + 1
        picked.append({"id": f"E{len(picked) + 1:03d}", "category": r["intent"], "question": r["text"], "expected": r["intent"]})
(HERE / "cases.jsonl").write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in picked), encoding="utf-8")
cats = sorted(count)
rates = {
    "v1": dict(zip(cats, [0.90, 0.88, 0.86, 0.92, 0.80, 0.90])),
    "v2": dict(zip(cats, [0.95, 0.93, 0.93, 0.95, 0.87, 0.95])),
    "v3": dict(zip(cats, [0.90, 0.40, 0.84, 0.92, 0.78, 0.88])),
}
(HERE / "sim_rates.json").write_text(json.dumps({"_note": "scripted pass probability per version and category, simulated", **rates}, indent=1) + "\n")
print(len(picked), cats)
