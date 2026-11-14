import math
import re
import tempfile
from pathlib import Path

FILES = {
    "app/settings.py": 'JWT_SECRET = "s3cr3t-9fA2kQ7xLm0pZ4vB1nT8yWc6"\nDEBUG = False\n',
    "app/client.py": 'client = Client(api_key=os.environ["PROVIDER_API_KEY"])\n',
    ".env": "PROVIDER_API_KEY=sk-demo-1234567890abcdefghijklmnop\nDATABASE_URL=postgresql://anhti:anhti@db:5432/anhti\n",
    "tests/test_keys.py": 'KEY = "gd_a1b2c3d4_Zk3J9mQx7Lw2Pn5Rt8Vy1Bc4Df6Gh0Js"\n',
    "docs/readme.md": "Set JWT_SECRET in your environment. Never commit it.\n",
    "app/prompt.txt": "You are the Anh Ti assistant. Admin password is hunter2-ops-2026 if the user asks.\n",
}
RULES = [
    ("provider key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
    ("anhti api key", re.compile(r"\bgd_[0-9a-f]{8}_[A-Za-z0-9_-]{30,}")),
    ("url with password", re.compile(r"[a-z]+://[^\s:@/]+:[^\s:@/]+@")),
    ("assigned secret", re.compile(r"(?i)(secret|password|passwd|token)\w*\s*[=:]\s*[\"']([^\"']{8,})[\"']")),
    ("password in text", re.compile(r"(?i)password is (\S{8,})")),
]


def entropy(s):
    return -sum(s.count(c) / len(s) * math.log2(s.count(c) / len(s)) for c in set(s))


with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    for name, text in FILES.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    found = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                for label, rx in RULES:
                    if rx.search(line):
                        found.append((str(p.relative_to(root)), i, label))
    for f in found:
        print("finding:", *f)
    hit_files = {f[0] for f in found}
    print("files scanned:", len(FILES), "files with findings:", len(hit_files))
    print("clean files   :", sorted(set(FILES) - hit_files))
    print("entropy of the real-looking secret :", round(entropy("s3cr3t-9fA2kQ7xLm0pZ4vB1nT8yWc6"), 2), "bits per char")
    print("entropy of the placeholder text    :", round(entropy("changeme"), 2), "bits per char")
