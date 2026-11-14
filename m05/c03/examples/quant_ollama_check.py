import csv
import time

import httpx

from _bench import MESSAGES, MODEL

LABELS = "change_address, complaint_late, eta, order_status, other, refund"
rows = [r for r in csv.DictReader(open(MESSAGES, encoding="utf-8")) if r["split"] == "test" and r["has_diacritics"] == "True"][:18]
info = httpx.post("http://localhost:11434/api/show", json={"model": MODEL}).json()
params = info["model_info"]["general.parameter_count"]
size = httpx.get("http://localhost:11434/api/tags").json()["models"][0]["size"]
print(f"{MODEL}: {info['details']['quantization_level']}, {params/1e9:.2f}B parameters, file {size/2**30:.2f} GiB, {size*8/params:.1f} bits per parameter")
right, toks, secs = 0, 0, 0.0
for r in rows:
    body = {"model": MODEL, "stream": False, "think": False, "options": {"num_predict": 8, "temperature": 0, "seed": 7},
            "messages": [{"role": "user", "content": f"Classify the message into one label from: {LABELS}. Answer with the label only.\nMessage: {r['text']}"}]}
    t0 = time.perf_counter()
    d = httpx.post("http://localhost:11434/api/chat", json=body, timeout=300).json()
    secs += time.perf_counter() - t0
    toks += d["eval_count"]
    right += d["message"]["content"].strip().lower() == r["intent"]
print(f"task: intent labels on {len(rows)} test messages, exact match {right}/{len(rows)} = {right/len(rows):.2f}")
print(f"generated {toks} tokens in {secs:.1f} s including prompt processing")
