import time

import _data
import _redactkit

texts = [r["text"] for r in _data.load()]
rounds = 20
start = time.perf_counter()
for _ in range(rounds):
    for text in texts:
        _redactkit.redact(text)
per_call_ms = (time.perf_counter() - start) * 1000 / (rounds * len(texts))
print(f"messages: {len(texts)}, average length {sum(map(len, texts)) / len(texts):.0f} characters")
print(f"redact() costs less than 0.5 ms per message: {per_call_ms < 0.5}")
print(f"so 1000 log lines add under half a second of CPU: {per_call_ms * 1000 / 1000 < 0.5}")
