import csv
import re
from pathlib import Path
from _sec import M05

CASES = M05.parent / "m04" / "data" / "cases.csv"
rows = list(csv.DictReader(CASES.open(encoding="utf-8", newline="")))[:40]
PHONE = re.compile(r"(?<!\d)0\d{9}(?!\d)")


def with_contact(i, r):
    phone = f"09{(i * 7919 + 1234567) % 100000000:08d}"
    return {**r, "phone": phone, "text": f"Khách {r['customer_name']} báo: {r['body']} Liên hệ {phone}."}


class Vault:
    def __init__(self):
        self.to_token, self.to_value = {}, {}

    def token(self, kind, value):
        if value not in self.to_token:
            t = f"[{kind}_{len(self.to_token) + 1}]"
            self.to_token[value] = t
            self.to_value[t] = value
        return self.to_token[value]

    def minimize(self, row):
        text = row["text"].replace(row["customer_name"], self.token("CUSTOMER", row["customer_name"]))
        return PHONE.sub(lambda m: self.token("PHONE", m.group(0)), text)

    def restore(self, text):
        for t, v in self.to_value.items():
            text = text.replace(t, v)
        return text


def leaks(prompt, row):
    return sum(1 for v in (row["customer_name"], row["phone"]) if v in prompt)


cases = [with_contact(i, r) for i, r in enumerate(rows)]
raw_leaks = sum(leaks(c["text"], c) for c in cases)
vault = Vault()
mini = [vault.minimize(c) for c in cases]
print("cases:", len(cases), "| items of personal data in prompts sent to the model")
print("  raw prompts      :", raw_leaks)
print("  minimized prompts:", sum(leaks(m, c) for m, c in zip(mini, cases)))
print("example sent  :", mini[0][:100])
reply = "Em đã ghi nhận khiếu nại của " + vault.token("CUSTOMER", cases[0]["customer_name"]) + ", sẽ gọi " + vault.token("PHONE", cases[0]["phone"]) + "."
print("model reply   :", reply)
print("shown to staff:", vault.restore(reply))
print("tokens in vault:", len(vault.to_value))
