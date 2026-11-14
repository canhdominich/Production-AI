import csv
import json
import time
from pathlib import Path

from openai import OpenAI

HERE = Path(__file__).resolve().parent
CACHE = HERE.parent / "data" / "tier_answers.json"
MESSAGES = HERE.parents[1] / ".." / "m02" / "data" / "messages.csv"
LABELS = ["order_status", "eta", "complaint_late", "refund", "change_address", "other"]
SYSTEM = (
    "You classify a customer message of a delivery company into exactly one intent.\n"
    "order_status: where the order is now. eta: when it will arrive. complaint_late: the order is late and the customer complains. "
    "refund: asks for money back. change_address: change address or receiver. other: anything else.\n"
    "A late order with an explicit request for money back is refund. Answer with the label only."
)
MODES = {"fast": "none", "deep": "low"}
PER_INTENT = 5

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama", timeout=180)


def pick_tasks():
    with open(MESSAGES.resolve(), encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["split"] == "test"]
    tasks = []
    for label in LABELS:
        tasks += sorted((r for r in rows if r["intent"] == label), key=lambda r: r["message_id"])[:PER_INTENT]
    return tasks


def ask(text, effort):
    t0 = time.perf_counter()
    r = client.responses.create(
        model="qwen3:1.7b",
        input=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}],
        reasoning={"effort": effort},
        max_output_tokens=800,
        temperature=0,
    )
    answer = r.output_text.strip().lower()
    pred = next((lab for lab in LABELS if lab in answer), "invalid")
    return {"pred": pred, "in_tokens": r.usage.input_tokens, "out_tokens": r.usage.output_tokens, "seconds": round(time.perf_counter() - t0, 1)}


def collect():
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    for t in pick_tasks():
        for mode, effort in MODES.items():
            key = f"{t['message_id']}:{mode}"
            if key not in cache:
                cache[key] = ask(t["text"], effort)
                CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return cache


if __name__ == "__main__":
    cache = collect()
    tasks = pick_tasks()
    print(f"tasks: {len(tasks)} test messages, {PER_INTENT} per intent, model qwen3:1.7b through Ollama")
    for mode in MODES:
        res = [cache[f"{t['message_id']}:{mode}"] for t in tasks]
        acc = sum(r["pred"] == t["intent"] for r, t in zip(res, tasks)) / len(tasks)
        print(f"{mode:5} accuracy {acc:.3f}  mean output tokens {sum(r['out_tokens'] for r in res) / len(res):6.1f}  mean seconds {sum(r['seconds'] for r in res) / len(res):5.1f}")
