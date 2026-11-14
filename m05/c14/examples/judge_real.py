import json
import re
import time

from openai import OpenAI

from _kit import DATA

CACHE = DATA / "judge_real_cache.json"
cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama", timeout=240)

PEAK = "Từ 01/11/2026 đến hết 15/12/2026, ngưỡng trễ để được bồi thường nâng từ 30 phút lên 45 phút."
CAP = "Hàng không khai báo giá trị: bồi thường tối đa 500.000 đồng mỗi đơn."
VOUCHER = "Voucher có giá trị 30.000 đồng cho đơn standard và 50.000 đồng cho đơn express, hạn dùng 60 ngày."
ITEMS = [
    ("peak-good", PEAK, "Đơn trễ 40 phút ngày 05/12/2026 có được bồi thường không?", "Chưa. Trong mùa cao điểm ngưỡng trễ là 45 phút, đơn trễ 40 phút chưa đủ điều kiện.", True),
    ("peak-bad", PEAK, "Đơn trễ 40 phút ngày 05/12/2026 có được bồi thường không?", "Có, đơn trễ trên 30 phút được bồi thường.", False),
    ("cap-good", CAP, "Hàng không khai báo giá trị được bồi thường tối đa bao nhiêu?", "Tối đa 500.000 đồng mỗi đơn.", True),
    ("cap-bad", CAP, "Hàng không khai báo giá trị được bồi thường tối đa bao nhiêu?", "Tối đa 2.000.000 đồng mỗi đơn.", False),
    ("voucher-good", VOUCHER, "Voucher express có giá trị bao nhiêu và dùng được bao lâu?", "50.000 đồng, dùng trong 60 ngày.", True),
    ("voucher-bad", VOUCHER, "Voucher express có giá trị bao nhiêu và dùng được bao lâu?", "Voucher đổi được thành tiền mặt, dùng không giới hạn thời gian.", False),
]
RUBRIC = ("Bạn là giám khảo. Chỉ dựa trên ĐOẠN TÀI LIỆU, phán quyết câu trả lời là pass (đúng với tài liệu và trả lời đúng câu hỏi) hoặc fail. "
          'Chỉ in một dòng JSON: {"verdict": "pass" hoặc "fail", "reason": "một câu"}.')


def judge(key, context, question, answer):
    if key not in cache:
        t0 = time.perf_counter()
        r = client.responses.create(model="qwen3:1.7b", reasoning={"effort": "none"}, max_output_tokens=120, instructions=RUBRIC,
                                    input=f"ĐOẠN TÀI LIỆU: {context}\nCÂU HỎI: {question}\nCÂU TRẢ LỜI: {answer}")
        cache[key] = {"text": r.output_text.strip(), "seconds": round(time.perf_counter() - t0, 1)}
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return cache[key]["text"]


agree = parsed = 0
for key, ctx, q, a, expected in ITEMS:
    text = judge(key, ctx, q, a)
    m = re.search(r'"verdict"\s*:\s*"(pass|fail)"', text)
    verdict = m.group(1) == "pass" if m else None
    parsed += verdict is not None
    agree += verdict == expected
    print(f"{key:13} human={'pass' if expected else 'fail'} judge={m.group(1) if m else 'unparsed':8} {text[:70]!r}")
print(f"parsed {parsed} of {len(ITEMS)}, agrees with the human label on {agree} of {len(ITEMS)}")
