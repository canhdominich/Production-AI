"""Generate synthetic customer messages with labelled personal data for the logging chapter (seed 42).

Every phone number, address and name below is invented from random digits and a fictional street list.
Each record keeps the exact character span of every piece of personal data, so a redactor can be scored.
"""
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
rnd = random.Random(42)

NAMES = ["Nguyễn Văn An", "Trần Thị Bình", "Lê Hoàng Lan", "Phạm Quang Minh", "Võ Thu Hà", "Đặng Minh Khoa", "Bùi Thanh Tâm"]
STREETS = ["Hoa Sen", "Hoa Mận", "Trăng Non", "Lúa Vàng", "Sao Mai", "Đường Mía", "Cá Rô", "Chè Xanh", "Dừa Xiêm"]
WARDS = ["Cầu Gỗ", "Xóm Vui", "Bến Sông", "Bãi Biển", "Chợ Mới", "Đồi Thông", "Đầu Phố"]
DISTRICTS = ["Đầu Phố", "Cầu Gỗ", "Xóm Vui", "Bến Sông", "Bãi Biển", "Chợ Mới", "Đồi Thông", "Khu Công Nghiệp"]
PREFIX = ["03", "05", "07", "08", "09"]


def strip_marks(text):
    import unicodedata
    out = []
    for ch in text:
        base = unicodedata.normalize("NFD", ch)[0]
        out.append("d" if ch == "đ" else "D" if ch == "Đ" else base)
    return "".join(out)


def phone():
    digits = rnd.choice(PREFIX) + str(rnd.randint(0, 9)) + "".join(str(rnd.randint(0, 9)) for _ in range(7))
    national, rest = digits, digits[1:]
    style = rnd.choices(["plain", "space4", "space3", "dots", "dash", "intl_plus", "intl_plus_space", "intl_paren", "intl_bare"], [34, 18, 8, 10, 6, 10, 6, 4, 4])[0]
    if style == "plain":
        return national
    if style == "space4":
        return f"{national[:4]} {national[4:7]} {national[7:]}"
    if style == "space3":
        return f"{national[:3]} {national[3:6]} {national[6:]}"
    if style == "dots":
        return f"{national[:4]}.{national[4:7]}.{national[7:]}"
    if style == "dash":
        return f"{national[:4]}-{national[4:7]}-{national[7:]}"
    if style == "intl_plus":
        return "+84" + rest
    if style == "intl_plus_space":
        return f"+84 {rest[:3]} {rest[3:6]} {rest[6:]}"
    if style == "intl_paren":
        return "(+84) " + rest
    return "84" + rest


def address():
    street, ward, dist = rnd.choice(STREETS), rnd.choice(WARDS), rnd.choice(DISTRICTS)
    n, m = rnd.randint(1, 240), rnd.randint(1, 60)
    form = rnd.choice(["full", "full", "slash", "alley", "block", "short"])
    if form == "full":
        return f"số {n} ngõ {m} đường {street}, phường {ward}, quận {dist}"
    if form == "slash":
        return f"{n}/{m} {street}, P. {ward}, Q. {dist}"
    if form == "alley":
        return f"hẻm {m} đường {street}, khu phố {rnd.randint(1, 9)}, phường {ward}"
    if form == "block":
        return f"chung cư {ward} tòa {rnd.choice('ABCD')} căn {rnd.randint(1, 25)}{rnd.randint(1, 12):02d}"
    return f"số {n} đường {street}, quận {dist}"


def order():
    return f"AT{rnd.randint(100000, 999999)}"


def money():
    return rnd.choice(["1.500.000đ", "250.000 đồng", "12.500.000đ", "480000 đồng", "35.000đ"])


T_PII = [
    ("Chào shop, mình là {name}, đơn {order} giao tới {address} chưa thấy đâu, gọi mình theo số {phone} nhé.", ["name", "address", "phone"]),
    ("Đơn {order} đổi nơi nhận sang {address}, liên hệ {phone}.", ["address", "phone"]),
    ("Em {name} đây, shipper cứ gọi {phone} khi tới nhé, hàng thu hộ {money}.", ["name", "phone"]),
    ("Hủy giúp mình đơn {order}, số điện thoại đặt hàng là {phone}.", ["phone"]),
    ("Giao lại đơn {order} tại {address} giúp mình, buổi tối mình mới có nhà.", ["address"]),
    ("sdt: {phone} - dia chi: {address} - don {order}", ["phone", "address"]),
    ("Mình {name}, địa chỉ nhận hàng {address}. Zalo {phone}. Hàng trị giá {money}.", ["name", "address", "phone"]),
    ("Anh {name} nhờ báo shipper giao {address}, gọi {phone} trước 15 phút.", ["name", "address", "phone"]),
]
T_PII_NODIAC = [
    ("shop oi don {order} giao toi {address} chua thay, goi minh so {phone} nhe", ["address", "phone"]),
    ("doi dia chi don {order} sang {address} giup minh", ["address"]),
    ("lien he {phone} khi giao hang, thu ho {money}", ["phone"]),
]
T_CLEAN = [
    "Đơn {order} đã quá hẹn giao 40 phút, mình muốn biết khi nào tới.",
    "Hàng bị móp thùng, phí ship {money} có được hoàn không?",
    "Shipper hẹn 17:30 ngày 10/11/2026 nhưng chưa thấy, đơn {order}.",
    "Cho mình hỏi chính sách bồi thường khi giao trễ trên 2 giờ.",
    "ma giam gia hom nay con dung duoc khong, don {order}",
    "Mình đặt 3 thùng, tổng 12kg, thu hộ {money}, đơn {order}.",
    "Tại sao đơn {order} báo đã giao mà mình chưa nhận?",
    "Voucher 30.000đ của đơn {order} dùng được tới khi nào?",
]


def build(n_pii=170, n_clean=70):
    records = []
    for i in range(n_pii):
        nodiac = i % 6 == 5
        tpl, kinds = rnd.choice(T_PII_NODIAC if nodiac else T_PII)
        values = {"name": rnd.choice(NAMES), "order": order(), "address": address(), "phone": phone(), "money": money()}
        if nodiac:
            values = {k: strip_marks(v).lower() if k in ("address", "name") else v for k, v in values.items()}
        text, spans, pos = "", [], 0
        for part in __import__("re").split(r"(\{[a-z]+\})", tpl):
            if part.startswith("{"):
                key = part[1:-1]
                val = values[key]
                if key in ("name", "address", "phone"):
                    spans.append({"kind": key, "text": val, "start": len(text), "end": len(text) + len(val)})
                text += val
            else:
                text += part
        records.append({"id": f"M{i:04d}", "text": text, "pii": spans})
    for j in range(n_clean):
        tpl = rnd.choice(T_CLEAN)
        text = tpl.format(order=order(), money=money())
        records.append({"id": f"M{n_pii + j:04d}", "text": text, "pii": []})
    rnd.shuffle(records)
    for k, r in enumerate(records):
        r["id"] = f"M{k:04d}"
    return records


if __name__ == "__main__":
    recs = build()
    (HERE / "support_messages.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8")
    kinds = {}
    for r in recs:
        for s in r["pii"]:
            kinds[s["kind"]] = kinds.get(s["kind"], 0) + 1
    print(len(recs), kinds)
