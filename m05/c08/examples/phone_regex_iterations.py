import re

import _data
import _redactkit

records = _data.load()
HARD_NEGATIVES = [
    "Mã giao dịch 7084123456789 đã thanh toán",
    "Doanh thu tháng 10.084.123.456đ",
    "Đơn AT084123456 giao lúc 08/04/2026",
    "Mã vận đơn TRK0912345678 đã quét kho",
    "Thu hộ 1.500.000đ, phí 35.000đ, đơn AT310007",
    "Hàng 12kg, 3 thùng, giao trước 17:30 ngày 10/11/2026",
]

VERSIONS = {
    "v1 ten digits only": re.compile(r"\b0\d{9}\b"),
    "v2 flexible, no boundary": re.compile(r"(?:\+84|84|0)[ .-]?[35789](?:[ .-]?\d){8}"),
    "v3 flexible + boundary": _redactkit.PHONE,
}

total = sum(1 for r in records for s in r["pii"] if s["kind"] == "phone")
print(f"{total} phone numbers in {len(records)} messages, {len(HARD_NEGATIVES)} hard negatives")
for name, rx in VERSIONS.items():
    hit = sum(1 for r in records for s in r["pii"] if s["kind"] == "phone" and any(m.start() <= s["start"] and m.end() >= s["end"] for m in rx.finditer(r["text"])))
    false_alarms = [t for t in HARD_NEGATIVES if rx.search(t)]
    print(f"{name:<26} recall {hit / total:5.1%}  false alarms {len(false_alarms)}/{len(HARD_NEGATIVES)}")

missed = [s["text"] for r in records for s in r["pii"] if s["kind"] == "phone" and not VERSIONS["v1 ten digits only"].search(s["text"])]
print("v1 misses, for example:", missed[:4])
print("v2 false alarm on:", [t for t in HARD_NEGATIVES if VERSIONS["v2 flexible, no boundary"].search(t)][0])
