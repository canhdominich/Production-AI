import re
import unicodedata


def fold(text):
    # Bỏ dấu từng ký tự nhưng giữ nguyên độ dài, nên vị trí khớp trên bản bỏ dấu dùng được cho bản gốc.
    return "".join("d" if ch == "đ" else "D" if ch == "Đ" else unicodedata.normalize("NFD", ch)[0] for ch in text)


PHONE = re.compile(r"(?<![\w.,/+-])(?:(?:\(\+84\)|\+84|84)[ .-]?|0)[35789](?:[ .-]?\d){8}(?!\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")

PLACE_WORDS = ("hoa sen man trang non lua vang sao mai duong mia ca ro che xanh dua xiem cau go xom vui "
               "ben song bai bien cho moi doi thong dau pho khu cong nghiep").split()
_W = "|".join(PLACE_WORDS)
PLACE = rf"(?:{_W})\b(?:\s+(?:{_W})\b){{0,3}}"
NUM = r"\d{1,4}[a-z]?(?!\d)"
KEYSEG = (rf"(?:(?:ngo|ngach|hem|kiet|thon|huyen|duong|phuong|quan|pho|tp\.|p\.|q\.)\s*(?:{NUM}|{PLACE})"
          rf"|khu\s+pho\s+{NUM}|chung\s+cu\s+(?:{PLACE})|toa\s+[a-z]\b|can\s+\d{{3,4}}(?!\d))")
HOUSE = rf"so\s+{NUM}(?:[/-]{NUM})*"
SLASH = rf"{NUM}(?:[/-]{NUM})+\s+(?={PLACE})"
SEP = r"(?:\s*,\s*|\s+)"
ELEM = rf"(?:{HOUSE}(?={SEP}{KEYSEG})|{SLASH}{PLACE}|{KEYSEG})"
ADDRESS = re.compile(rf"(?<![\w/.]){ELEM}(?:{SEP}(?:{ELEM}|{PLACE}))*")


def find(text):
    found = [(m.start(), m.end(), "phone") for m in PHONE.finditer(text)]
    found += [(m.start(), m.end(), "email") for m in EMAIL.finditer(text)]
    found += [(m.start(), m.end(), "address") for m in ADDRESS.finditer(fold(text).lower())]
    return sorted(found)


def redact(text):
    out, pos = [], 0
    for start, end, kind in find(text):
        if start < pos:
            continue
        out += [text[pos:start], f"[{kind}]"]
        pos = end
    return "".join(out) + text[pos:]
