from openai import OpenAI

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama", timeout=180, max_retries=0)
QUESTION = "Đơn giao trễ thì khách được bồi thường tối đa bao nhiêu phần trăm giá trị đơn? Trả lời một câu."

for label, extra in (("default", {}), ("reasoning_effort=none", {"reasoning_effort": "none"})):
    r = client.chat.completions.create(model="qwen3:1.7b", temperature=0, seed=7, max_tokens=60,
                                       messages=[{"role": "user", "content": QUESTION}], **extra)
    choice = r.choices[0]
    print(f"{label:<22} finish={choice.finish_reason:<6} tokens_out={r.usage.completion_tokens:>3} content_chars={len(choice.message.content or ''):>3}  {(choice.message.content or '')[:50]!r}")
