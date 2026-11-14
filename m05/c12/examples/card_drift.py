import json
import shutil
import tempfile
from pathlib import Path

from _card import M05, build_card, config_digest, lint_card

card = build_card()
tmp = Path(tempfile.mkdtemp(prefix="m05c12_"))
shutil.copy(M05 / "data" / "tenants.json", tmp / "tenants.json")
prices = json.loads((M05 / "data" / "prices.json").read_text(encoding="utf-8"))
prices["models"]["fake-medium"]["output_per_mtok"] = 2.40
(tmp / "prices.json").write_text(json.dumps(prices), encoding="utf-8")

print("card vs shipped config:", lint_card(card, config_digest()) or "up to date")
print("card vs edited config :", lint_card(card, config_digest(tmp)))
shutil.rmtree(tmp)
