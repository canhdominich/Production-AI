import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "platform"))
from common import estimate_prompt_tokens, estimate_tokens, messages_text
from gateway_core import PriceTable
from workload import SYSTEM, generate, sources

MIN_CACHE_TOKENS = 1024
GRANULARITY = 128
prices = PriceTable()
reqs = generate(3000, seed=42)
policy = "\n\n".join(sources()["chunks"])


def cached_part(prompt_tokens, prefix_tokens):
    if prompt_tokens < MIN_CACHE_TOKENS:
        return 0
    return prefix_tokens // GRANULARITY * GRANULARITY


def report(name, rs, texts, prompts):
    prefix_chars = len(os.path.commonprefix(texts))
    prefix_tokens = estimate_tokens(texts[0][:prefix_chars])
    cached = [cached_part(p, prefix_tokens) for p in prompts]
    models = [r.model for r in rs]
    plain = sum(prices.cost(m, p, 0) for m, p in zip(models, prompts))
    with_cache = sum(prices.cost(m, p, 0, c) for m, p, c in zip(models, prompts, cached))
    eligible = sum(c > 0 for c in cached) / len(rs)
    print(f"{name:34} prompt avg {sum(prompts) / len(rs):6.0f}  stable prefix {prefix_tokens:5d}  eligible {eligible:5.0%}  "
          f"input cost per 1000 requests ${plain / len(rs) * 1000:.3f} to ${with_cache / len(rs) * 1000:.3f}")


chat = [r for r in reqs if r.feature == "chat"]
report("chat (system prompt first)", chat, [messages_text(r.messages) for r in chat], [r.prompt_tokens for r in chat])

ka = [r for r in reqs if r.feature == "knowledge_assistant"]
report("knowledge, random passages first", ka, [messages_text(r.messages) for r in ka], [r.prompt_tokens for r in ka])

fixed = []
for r in ka:
    question = r.messages[-1]["content"].split("Câu hỏi:")[-1].strip()
    fixed.append([{"role": "system", "content": SYSTEM["knowledge_assistant"]},
                  {"role": "user", "content": f"Tài liệu:\n{policy}\n\nCâu hỏi: {question}"}])
report("knowledge, fixed policy first", ka, [messages_text(m) for m in fixed], [estimate_prompt_tokens(m) for m in fixed])
