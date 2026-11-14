import time

from openai import OpenAI

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama", timeout=120)
PROMPT = "Khách hỏi: 'Đơn AT123456 trễ rồi, giờ sao?'. Trả lời một câu ngắn bằng tiếng Việt."


def ask(temperature, seed=None):
    t0 = time.perf_counter()
    extra = {"seed": seed} if seed is not None else {}
    r = client.responses.create(model="qwen3:1.7b", input=PROMPT, reasoning={"effort": "none"}, max_output_tokens=60, temperature=temperature, extra_body=extra)
    return r.output_text.strip().replace("\n", " ")[:90], r.usage.output_tokens, time.perf_counter() - t0


for label, temp, seed in (("temp 0.9, no seed", 0.9, None), ("temp 0.9, no seed", 0.9, None), ("temp 0.9, no seed", 0.9, None), ("temp 0, seed 7", 0.0, 7), ("temp 0, seed 7", 0.0, 7)):
    text, n, sec = ask(temp, seed)
    print(f"{label:<18} {n:>3} tok {sec:5.1f}s  {text}")
