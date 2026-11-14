import csv
import httpx

from _bench import MESSAGES, MODEL

rows = [r["text"] for r in csv.DictReader(open(MESSAGES, encoding="utf-8")) if r["has_diacritics"] == "True"]
def policy(tag):
    return "\n".join(f"Quy tắc {i} (bản {tag}): nhân viên chăm sóc khách hàng của Giao Hàng Anh Tí luôn xin lỗi trước, xác nhận mã đơn, nêu thời gian dự kiến và không hứa hoàn tiền khi chưa kiểm tra." for i in range(1, 13))


def call(system, question):
    body = {"model": MODEL, "stream": False, "think": False, "keep_alive": "5m", "options": {"num_predict": 4, "temperature": 0},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": question}]}
    r = httpx.post("http://localhost:11434/api/chat", json=body, timeout=600).json()
    return r["prompt_eval_count"], r["prompt_eval_duration"] / 1e9


call("ping", "ping")
cold, hit, miss = [], [], []
tokens = 0
for k in range(4):
    p = policy(f"{k}")
    edited = p.replace("Quy tắc 1 (bản", "Quy tắc mới 1 (bản", 1)
    tokens, c = call(p, rows[3 * k])
    cold.append(c)
    hit.append(call(p, rows[3 * k + 1])[1])
    miss.append(call(edited, rows[3 * k + 2])[1])
print(f"policy prefix about {tokens} tokens, 4 trials, prefill seconds as reported by Ollama")
print("trial  cold prefix  same prefix, new question  prefix edited at line 1")
for k in range(4):
    print(f"{k + 1:>5}  {cold[k]:11.2f}  {hit[k]:25.2f}  {miss[k]:23.2f}")
med = lambda xs: sorted(xs)[len(xs) // 2]
print(f"median {med(cold):11.2f}  {med(hit):25.2f}  {med(miss):23.2f}")
