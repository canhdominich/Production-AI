import json
import re
import time

from openai import OpenAI

from _genai import PolicyIndex
from _support import DATA

CACHE = DATA / "llm_cache_wrong_but_200.json"
cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama", timeout=180)
index = PolicyIndex()

CASES = [
    ("peak", "Đơn standard trễ 40 phút, giao ngày 05/12/2026. Khách có được bồi thường không?", "neg", "không"),
    ("peak", "Đơn express trễ 35 phút, giao ngày 20/11/2026. Khách có được bồi thường không?", "neg", "không"),
    ("plain", "Hàng không khai báo giá trị được bồi thường tối đa bao nhiêu mỗi đơn?", "has", "500.000"),
    ("plain", "Voucher có hạn dùng bao lâu?", "has", "60 ngày"),
]


def ask(question, context, k):
    key = f"{k}|{question}"
    if key not in cache:
        t0 = time.perf_counter()
        r = client.responses.create(
            model="qwen3:1.7b", reasoning={"effort": "none"}, max_output_tokens=120,
            instructions="Trả lời ngắn bằng tiếng Việt, chỉ dựa trên ngữ cảnh.",
            input=f"Ngữ cảnh:\n{context}\n\nCâu hỏi: {question}")
        cache[key] = {"text": r.output_text.strip(), "seconds": round(time.perf_counter() - t0, 1)}
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return cache[key]["text"]


def ok(answer, kind, expected):
    a = answer.lower().replace("*", "")
    if kind == "neg":
        return bool(re.search(r"không (được|có|bồi thường)", a)) and not a.startswith("có")
    return expected in a


for k in (1, 3):
    print(f"--- retrieval top_k = {k}")
    passed = 0
    for tag, q, kind, expected in CASES:
        hits = index.search(q, k)
        ids = [re.match(r"\*\*(CS-[A-Z0-9-]+@v\d#\d)", c).group(1) for _, _, c in hits]
        a = ask(q, "\n".join(c for _, _, c in hits), k)
        good = ok(a, kind, expected)
        passed += good
        print(f"[{tag:5}] HTTP 200 | {'right' if good else 'WRONG'} | docs={','.join(ids)} | {a[:60]!r}")
    print(f"HTTP errors 0 of {len(CASES)}, right answers {passed} of {len(CASES)}")
