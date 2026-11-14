import _data
import _redactkit

records = _data.load()
finder = lambda text: [(a, b) for a, b, kind in _redactkit.find(text) if kind == "address"]
tp, fp, fn = _data.score(records, finder, "address")
clean = [r for r in records if not r["pii"]]
print(f"labelled addresses: {tp + fn}, caught {tp}, missed {fn}, extra masks {fp}")
print(f"clean messages changed by redact(): {sum(1 for r in clean if _redactkit.redact(r['text']) != r['text'])} of {len(clean)}")

HELD_OUT = [
    "Giao tới số 9 ngõ 14 đường Mây Trắng, phường Cầu Gỗ nhé",
    "nha ngay canh Cong Vien Dau Pho, goi chu Tu giup minh",
    "Địa chỉ: 45 Thạch Thảo, P. Xóm Vui",
    "Chi nhánh quận Đầu Phố có mở thứ bảy không?",
    "Nhà mình gần Cầu Gỗ, ship nhanh giúp mình",
    "Đơn AT310007 nặng 12kg, giao hẻm 25 đường Sao Mai",
]
print("held-out messages the generator never produced:")
for text in HELD_OUT:
    print("  in :", text)
    print("  out:", _redactkit.redact(text))
