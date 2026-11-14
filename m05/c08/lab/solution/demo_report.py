import json
from pathlib import Path

import safe_logging as sl
from lab_app import make_system

DATA = Path(__file__).resolve().parents[2] / "data" / "support_messages.jsonl"
records = [json.loads(line) for line in DATA.read_text(encoding="utf-8").splitlines()]

client, api_buf, tools_buf = make_system()
trace_ids, secrets_ = [], []
for i, rec in enumerate(records):
    body = {"tenant_id": "br-cau-go", "text": rec["text"], "order_id": f"AT31{i:04d}"}
    trace_ids.append(client.post("/chat", json=body).json()["trace_id"])
    secrets_ += [s["text"] for s in rec["pii"] if s["kind"] in ("phone", "address")]

lines = api_buf.getvalue().splitlines() + tools_buf.getvalue().splitlines()
rows = [json.loads(x) for x in lines]
by_trace = {}
for row in rows:
    by_trace.setdefault(row["trace_id"], set()).add(row["service"])
print(f"requests: {len(records)}, log lines: {len(lines)}, distinct trace ids: {len(set(trace_ids))}")
print("every trace id appears in both services:", all(s == {"api", "tools"} for s in by_trace.values()))
print("lines without trace_id:", sum(1 for r in rows if "trace_id" not in r))
print(f"phone and address values checked: {len(set(secrets_))}, found in logs: {len(sl.find_leaks(lines, secrets_))}")
print("sample line:", rows[1]["event"][:80])
