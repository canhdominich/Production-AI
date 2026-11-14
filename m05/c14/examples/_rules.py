import subprocess

import yaml

from _kit import HERE

RULES_DIR = HERE.parent / "rules"
COMPOSE = HERE.parent / "stack" / "compose.yaml"
AVAILABILITY_BUDGET = 0.005
QUALITY_BUDGET = 0.30
ERROR_WINDOWS = ("5m", "30m", "1h", "2h", "6h", "1d", "3d")
RUNBOOK = "docs/runbooks/llm-slo.md"


class Literal(str):
    pass


yaml.add_representer(Literal, lambda d, v: d.represent_scalar("tag:yaml.org,2002:str", str(v), style="|"), Dumper=yaml.SafeDumper)


def burn(ratio, rate, budget):
    return f"{ratio} > ({rate} * {budget})"


def recording_rules():
    rules = []
    for w in ERROR_WINDOWS:
        rules.append({"record": f"llm:error_ratio_rate{w}",
                      "expr": f'sum(rate(llm_requests_total{{status="error"}}[{w}])) / sum(rate(llm_requests_total[{w}]))'})
    for w in ("1d", "3d"):
        rules.append({"record": f"llm:eval_fail_ratio_rate{w}",
                      "expr": f'sum(increase(llm_eval_samples_total{{verdict="fail"}}[{w}])) / sum(increase(llm_eval_samples_total[{w}]))'})
    return rules


def alert(name, expr, severity, slo, summary, wait):
    return {"alert": name, "expr": Literal(expr + "\n"), "for": wait, "labels": {"severity": severity, "slo": slo},
            "annotations": {"summary": summary, "runbook": RUNBOOK}}


def alert_rules(budget=AVAILABILITY_BUDGET):
    b = budget
    fast = (f"({burn('llm:error_ratio_rate1h', 14.4, b)} and {burn('llm:error_ratio_rate5m', 14.4, b)})\nor\n"
            f"({burn('llm:error_ratio_rate6h', 6, b)} and {burn('llm:error_ratio_rate30m', 6, b)})")
    slow = (f"({burn('llm:error_ratio_rate1d', 3, b)} and {burn('llm:error_ratio_rate2h', 3, b)})\nor\n"
            f"({burn('llm:error_ratio_rate3d', 1, b)} and {burn('llm:error_ratio_rate6h', 1, b)})")
    quality = (f"{burn('llm:eval_fail_ratio_rate3d', 1, QUALITY_BUDGET)} and {burn('llm:eval_fail_ratio_rate1d', 1, QUALITY_BUDGET)}\n"
               "and sum(increase(llm_eval_samples_total[1d])) >= 20")
    return [
        alert("LLMAvailabilityFastBurn", fast, "page", "availability", "Error budget is burning fast, users see failures now", "2m"),
        alert("LLMAvailabilitySlowBurn", slow, "ticket", "availability", "Error budget is leaking slowly", "15m"),
        alert("LLMQualityBurn", quality, "ticket", "quality", "Sampled answers fail more often than the quality SLO allows", "1h"),
        alert("LLMEvalPipelineStalled", "sum(increase(llm_eval_samples_total[1d])) == 0", "ticket", "quality", "No answers were judged in the last day", "30m"),
        alert("LLMInputDrift", "max by (feature) (llm_input_psi) > 0.25", "ticket", "drift", "The question mix moved away from the reference week", "1d"),
    ]


def rules_document():
    return {"groups": [{"name": "llm-slo-recording", "interval": "1m", "rules": recording_rules()},
                       {"name": "llm-slo-alerts", "interval": "1m", "rules": alert_rules()}]}


def write_yaml(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, sort_keys=False, width=200, allow_unicode=True), encoding="utf-8")


def promtool(*args):
    cmd = ["docker", "compose", "-p", "m05c14", "-f", str(COMPOSE), "run", "--rm", "-T", "promtool", *args]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    lines = [x for x in (r.stdout + r.stderr).splitlines() if x.strip() and not x.lstrip().startswith(("Network", "Container"))]
    return r.returncode, "\n".join(lines)
