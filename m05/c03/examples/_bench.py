import csv
import json
import sys
import threading
import time
from pathlib import Path

import httpx

PLATFORM = str(Path(__file__).resolve().parents[2] / "platform")
if PLATFORM not in sys.path:
    sys.path.insert(0, PLATFORM)

URL = "http://localhost:11434/v1/responses"
MODEL = "qwen3:1.7b"
DATA = Path(__file__).resolve().parents[1] / "data"
MESSAGES = Path(__file__).resolve().parents[3] / "m02" / "data" / "messages.csv"


def prompts(n):
    rows = [r for r in csv.DictReader(open(MESSAGES, encoding="utf-8")) if r["has_diacritics"] == "True" and r["split"] == "train"]
    return ["Khách nhắn: '%s'. Trả lời ngắn gọn bằng tiếng Việt." % r["text"] for r in rows[:n]]


def one(prompt, max_tokens=24, results=None, start_gate=None):
    if start_gate:
        start_gate.wait()
    body = {"model": MODEL, "input": prompt, "reasoning": {"effort": "none"}, "max_output_tokens": max_tokens, "stream": True}
    t0 = time.perf_counter()
    first = last = None
    n_out = n_in = 0
    with httpx.stream("POST", URL, json=body, timeout=900) as r:
        event = None
        for line in r.iter_lines():
            if line.startswith("event:"):
                event = line[7:].strip()
            elif line.startswith("data:") and event == "response.output_text.delta":
                now = time.perf_counter()
                first = first or now
                last = now
            elif line.startswith("data:") and event == "response.completed":
                u = json.loads(line[5:])["response"]["usage"]
                n_out, n_in = u["output_tokens"], u["input_tokens"]
    end = time.perf_counter()
    rec = dict(start=0.0, ttft=first - t0, last=last - t0, total=end - t0, n_out=n_out, n_in=n_in)
    rec["tpot"] = (last - first) / (n_out - 1) if n_out > 1 and last > first else 0.0
    if results is not None:
        results.append(rec)
    return rec


def run_concurrent(prompts_list, max_tokens=24):
    gate, results = threading.Event(), []
    ths = [threading.Thread(target=one, args=(p, max_tokens, results, gate)) for p in prompts_list]
    [t.start() for t in ths]
    time.sleep(0.2)
    t0 = time.perf_counter()
    gate.set()
    [t.join() for t in ths]
    return results, time.perf_counter() - t0
