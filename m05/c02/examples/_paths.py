import sys
from pathlib import Path

PLATFORM = str(Path(__file__).resolve().parents[2] / "platform")
C01 = str(Path(__file__).resolve().parents[2] / "c01" / "examples")
for p in (PLATFORM, C01):
    if p not in sys.path:
        sys.path.insert(0, p)
