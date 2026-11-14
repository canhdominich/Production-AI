from _card import LAB, M05, rows, sha

FILES = [
    ("m05 tenants", M05 / "data" / "tenants.json", "invented"),
    ("m05 prices", M05 / "data" / "prices.json", "invented, illustrative"),
    ("m02 messages", LAB / "m02" / "data" / "messages.csv", "synthetic"),
    ("m03 questions", LAB / "m03" / "data" / "questions.csv", "synthetic"),
    ("m04 cases", LAB / "m04" / "data" / "cases.csv", "synthetic"),
]
print(f"{'dataset':<14}{'rows':>6}  {'sha256 (16)':<18}origin")
for name, path, origin in FILES:
    n = rows(path) if path.suffix == ".csv" else "-"
    print(f"{name:<14}{n:>6}  {sha(path)[:16]:<18}{origin}")
