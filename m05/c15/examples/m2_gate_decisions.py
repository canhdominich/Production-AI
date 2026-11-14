import tomllib

import _kit
from anhti_platform import evalgate

E = _kit.PROJECT / "evals"
cases = evalgate.load_cases(E / "cases.jsonl")
rates = __import__("json").loads((E / "sim_rates.json").read_text())
cfg = tomllib.loads((E / "thresholds.toml").read_text())["gate"]
base = evalgate.run_cases(cases, evalgate.scripted_model("v1", rates))
print("cases:", len(cases), "| thresholds:", cfg)
print(f"baseline v1 pass rate: {evalgate.pass_rate(base):.3f}")
for version in ("v2", "v3"):
    rep = evalgate.decide(base, evalgate.run_cases(cases, evalgate.scripted_model(version, rates)), **cfg)
    print(f"\ncandidate {version}: {rep['decision'].upper()} pass rate {rep['candidate']}")
    print("  by category:", ", ".join(f"{k} {v}" for k, v in rep["by_category"].items()))
    for reason in rep["reasons"]:
        print("  reason:", reason)
