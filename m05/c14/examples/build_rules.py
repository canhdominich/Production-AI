import re

import yaml

from _rules import RULES_DIR, alert_rules, promtool, recording_rules, rules_document, write_yaml

write_yaml(RULES_DIR / "llm_slo.rules.yml", rules_document())
text = (RULES_DIR / "llm_slo.rules.yml").read_text(encoding="utf-8")
start = text.rfind("\n", 0, text.index("- alert: LLMAvailabilityFastBurn")) + 1
print(text[start:text.index("- alert: LLMAvailabilitySlowBurn")].rstrip())
print()

code, out = promtool("check", "rules", "/rules/llm_slo.rules.yml")
print("promtool check rules:", re.sub(r"\s+", " ", out).strip())

broken = yaml.safe_load(text)
broken["groups"][1]["rules"][0]["expr"] = "(llm:error_ratio_rate1h > (14.4 * 0.005) and llm:error_ratio_rate5m > (14.4 * 0.005)"
write_yaml(RULES_DIR / "_broken.rules.yml", broken)
code, out = promtool("check", "rules", "/rules/_broken.rules.yml")
print("\nsame file with one missing parenthesis, exit code", code)
print("\n".join(x for x in out.splitlines() if x.strip())[:420])
(RULES_DIR / "_broken.rules.yml").unlink()
print(f"\n{len(recording_rules())} recording rules and {len(alert_rules())} alert rules generated from Python")
