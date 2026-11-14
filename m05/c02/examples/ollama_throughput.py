import threading
import time

from openai import OpenAI

import _paths  # noqa: F401
from common import load_json

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama", timeout=180)
PROMPT = "Viết một đoạn khoảng 100 từ giải thích vì sao đơn hàng giao trễ vào giờ cao điểm."


def one_call(out, i):
    t0 = time.perf_counter()
    r = client.chat.completions.create(model="qwen3:1.7b", temperature=0, seed=7, max_tokens=120, reasoning_effort="none",
                                       messages=[{"role": "user", "content": PROMPT + f" (lần {i})"}])
    out.append((r.usage.completion_tokens, time.perf_counter() - t0))


def run(parallel):
    out = []
    threads = [threading.Thread(target=one_call, args=(out, i)) for i in range(parallel)]
    t0 = time.perf_counter()
    [t.start() for t in threads]
    [t.join() for t in threads]
    wall = time.perf_counter() - t0
    tokens = sum(n for n, _ in out)
    return tokens, wall


one_call([], 99)
CPU_VM_PER_HOUR = 0.20
price_small_out = load_json("prices.json")["models"]["fake-small"]["output_per_mtok"]
print("parallel   output tokens   wall seconds   tokens per second   USD per 1M output tokens (CPU VM at 0.20 USD/h)")
for parallel in (1, 3):
    tokens, wall = run(parallel)
    tps = tokens / wall
    cost = CPU_VM_PER_HOUR / (tps * 3600) * 1_000_000
    print(f"{parallel:>8} {tokens:>15} {wall:14.1f} {tps:19.1f} {cost:46.2f}")
print(f"\nillustrative API price of fake-small: {price_small_out:.2f} USD per 1M output tokens")
