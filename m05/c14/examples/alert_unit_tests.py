import re

from _rules import RULES_DIR, promtool, rules_document, write_yaml


def counters(per_minute, error_share, minutes):
    ok, err, a, b = [0.0], [0.0], 0.0, 0.0
    for m in range(minutes):
        share = error_share(m)
        a += per_minute * (1 - share)
        b += per_minute * share
        ok.append(round(a, 3))
        err.append(round(b, 3))
    return " ".join(map(str, ok)), " ".join(map(str, err))


def series(ok, err):
    return [{"series": 'llm_requests_total{feature="chat",status="ok"}', "values": ok},
            {"series": 'llm_requests_total{feature="chat",status="error"}', "values": err}]


def expect(at, name, firing, severity="page", slo="availability"):
    exp = [{"exp_labels": {"severity": severity, "slo": slo}, "exp_annotations": ALERT_NOTES[name]}] if firing else []
    return {"eval_time": at, "alertname": name, "exp_alerts": exp}


NOTES = {r["alert"]: r["annotations"] for g in rules_document()["groups"] for r in g["rules"] if "alert" in r}
ALERT_NOTES = NOTES
fast = "LLMAvailabilityFastBurn"
outage = series(*counters(4, lambda m: 0.40 if 120 <= m < 135 else 0.001, 180))
blip = series(*counters(4, lambda m: 1.0 if 100 <= m < 102 else 0.001, 180))
HOURLY = 40 / 24
fail_h, pass_h = [0.0], [0.0]
for h in range(96):
    rate = 0.24 if h < 24 else 0.46
    fail_h.append(round(fail_h[-1] + HOURLY * rate, 3))
    pass_h.append(round(pass_h[-1] + HOURLY * (1 - rate), 3))
quality = [{"series": 'llm_eval_samples_total{feature="knowledge_assistant",verdict="pass"}', "values": " ".join(map(str, pass_h))},
           {"series": 'llm_eval_samples_total{feature="knowledge_assistant",verdict="fail"}', "values": " ".join(map(str, fail_h))}]
judged = [str(i) for i in range(145)] + ["144"] * 215
stalled = [{"series": 'llm_eval_samples_total{feature="chat",verdict="pass"}', "values": " ".join(judged)}]

tests = {"evaluation_interval": "1m", "rule_files": ["llm_slo.rules.yml"], "tests": [
    {"interval": "1m", "name": "outage: 40% failures for 15 minutes, then recovery", "input_series": outage,
     "alert_rule_test": [expect("125m", fast, False), expect("140m", fast, True), expect("175m", fast, False)]},
    {"interval": "1m", "name": "blip: 2 minutes of failures at 4 requests a minute", "input_series": blip,
     "alert_rule_test": [expect("104m", fast, False), expect("110m", fast, False), expect("130m", fast, False)]},
    {"interval": "1h", "name": "quality: failures go from 24% to 46% of sampled answers after day 1", "input_series": quality,
     "alert_rule_test": [expect("20h", "LLMQualityBurn", False, "ticket", "quality"), expect("90h", "LLMQualityBurn", True, "ticket", "quality")]},
    {"interval": "10m", "name": "the judging job stops after day 1", "input_series": stalled,
     "alert_rule_test": [expect("30h", "LLMEvalPipelineStalled", False, "ticket", "quality"), expect("59h", "LLMEvalPipelineStalled", True, "ticket", "quality")]},
]}
write_yaml(RULES_DIR / "llm_slo.tests.yml", tests)
write_yaml(RULES_DIR / "llm_slo.rules.yml", rules_document())
code, out = promtool("test", "rules", "/rules/llm_slo.tests.yml")
print("promtool test rules, exit code", code)
print(re.sub(r"\n\s*\n", "\n", out)[:900])

naive = rules_document()
naive["groups"][1]["rules"][0]["expr"] = "llm:error_ratio_rate1h > (14.4 * 0.005)\n"
write_yaml(RULES_DIR / "_naive.rules.yml", naive)
write_yaml(RULES_DIR / "_naive.tests.yml", {"evaluation_interval": "1m", "rule_files": ["_naive.rules.yml"], "tests": [tests["tests"][0]]})
code, out = promtool("test", "rules", "/rules/_naive.tests.yml")
print("\nsame tests against a rule that only looks at the 1 hour window, exit code", code)
print("\n".join(x for x in out.splitlines() if x.strip() and "Annotations" not in x))
for name in ("_naive.rules.yml", "_naive.tests.yml"):
    (RULES_DIR / name).unlink()
