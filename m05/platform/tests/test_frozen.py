import hashlib
from pathlib import Path

M05 = Path(__file__).resolve().parents[2]
MANIFEST = M05 / "FROZEN.sha256"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_files_unchanged():
    expected = dict(line.split("  ", 1)[::-1] for line in MANIFEST.read_text().splitlines() if line.strip())
    assert expected, "manifest is empty"
    changed = [name for name, want in expected.items() if not (M05 / name).exists() or digest(M05 / name) != want]
    assert not changed, f"frozen shared base was modified: {changed}. Extend it from your own chapter folder instead of editing it."


def test_no_unlisted_files_in_frozen_folders():
    listed = {line.split("  ", 1)[1] for line in MANIFEST.read_text().splitlines() if line.strip() and line.split("  ", 1)[1] != "README.md"}
    found = {str(p.relative_to(M05)) for folder in ("data", "platform") for p in (M05 / folder).rglob("*")
             if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
    assert found == listed, f"unlisted or missing: {sorted(found ^ listed)}"
