import json
import re
from pathlib import Path

import yaml

from anhti_platform import evalgate

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"
EVALS = ROOT / "evals"


def results(rate_by_cat, n=15):
    out = []
    for cat, rate in rate_by_cat.items():
        k = round(rate * n)
        out += [{"id": f"{cat}{i}", "category": cat, "ok": i < k} for i in range(n)]
    return out


BASE = {"a": 0.9, "b": 0.9, "c": 0.9, "d": 0.9}


def test_gate_deploys_an_equal_or_better_candidate():
    better = {**BASE, "a": 1.0}
    assert evalgate.decide(results(BASE), results(better))["decision"] == "deploy"
    assert evalgate.decide(results(BASE), results(BASE))["decision"] == "deploy"


def test_gate_blocks_an_overall_drop():
    worse = {k: 0.8 for k in BASE}
    report = evalgate.decide(results(BASE), results(worse), min_pass=0.7)
    assert report["decision"] == "block"
    assert any("overall drop" in r for r in report["reasons"])


def test_gate_blocks_one_category_that_collapses_inside_a_good_average():
    broken = {**BASE, "a": 0.4, "b": 1.0, "c": 1.0, "d": 1.0}
    report = evalgate.decide(results(BASE), results(broken))
    assert report["decision"] == "block"
    assert any("category a" in r for r in report["reasons"])


def test_gate_blocks_when_too_few_cases_were_run():
    report = evalgate.decide(results(BASE, 5), results(BASE, 5))
    assert report["decision"] == "block"
    assert any("cases" in r for r in report["reasons"])


def test_gate_blocks_below_the_absolute_floor_even_without_regression():
    low = {k: 0.7 for k in BASE}
    assert evalgate.decide(results(low), results(low))["decision"] == "block"


def test_cli_exit_code_follows_the_decision(capsys):
    args = ["--cases", str(EVALS / "cases.jsonl"), "--rates", str(EVALS / "sim_rates.json"), "--thresholds", str(EVALS / "thresholds.toml")]
    assert evalgate.main(args + ["--candidate", "v2"]) == 0
    assert evalgate.main(args + ["--candidate", "v3"]) == 1
    assert json.loads(capsys.readouterr().out.split("\n}\n")[-2] + "\n}")["decision"] == "block"


def test_eval_set_covers_every_intent_with_enough_cases():
    cases = evalgate.load_cases(EVALS / "cases.jsonl")
    per = {}
    for c in cases:
        per[c["category"]] = per.get(c["category"], 0) + 1
    assert len(cases) >= 60 and len(per) == 6 and min(per.values()) >= 10


def workflow():
    return yaml.safe_load((DEPLOY / "ci.yml").read_text())


def test_deploy_job_cannot_start_before_tests_and_the_eval_gate():
    jobs = workflow()["jobs"]
    chain, job = [], "deploy"
    while job:
        need = jobs[job].get("needs")
        chain.append(job)
        job = need if isinstance(need, str) else None
    assert chain == ["deploy", "build", "eval-gate", "test"]


def test_deploy_runs_only_from_main_and_in_a_protected_environment():
    deploy = workflow()["jobs"]["deploy"]
    assert "refs/heads/main" in deploy["if"]
    assert deploy["environment"] == "production"


def test_eval_gate_job_runs_the_gate_module_and_keeps_the_report():
    steps = workflow()["jobs"]["eval-gate"]["steps"]
    text = json.dumps(steps)
    assert "anhti_platform.evalgate" in text and "upload-artifact" in text


def test_workflow_holds_no_literal_secret():
    text = (DEPLOY / "ci.yml").read_text()
    assert not re.search(r"(password|secret|token|key)\s*[:=]\s*['\"]?[A-Za-z0-9]{12,}", text, re.I)


def compose():
    return yaml.safe_load((DEPLOY / "compose.yaml").read_text())


def test_compose_secrets_come_from_the_environment_not_the_file():
    env = compose()["services"]["api"]["environment"]
    for name in ("JWT_SECRET", "KEY_PEPPER", "DEMO_PASSWORD"):
        assert env[name].startswith("${") and ":?" in env[name]
    assert ":?" in compose()["services"]["postgres"]["environment"]["POSTGRES_PASSWORD"]


def test_only_caddy_listens_on_public_interfaces():
    for name, svc in compose()["services"].items():
        for port in svc.get("ports", []):
            if name == "caddy":
                continue
            assert str(port).startswith("127.0.0.1:"), f"{name} publishes {port}"


def test_api_waits_for_healthy_dependencies_and_has_a_healthcheck():
    api = compose()["services"]["api"]
    assert all(v["condition"] == "service_healthy" for v in api["depends_on"].values())
    for dep in ("postgres", "redis", "provider-primary", "provider-secondary"):
        assert "healthcheck" in compose()["services"][dep]
    assert "HEALTHCHECK" in (DEPLOY / "Dockerfile").read_text()


def test_image_runs_as_non_root_and_bakes_no_secret():
    text = (DEPLOY / "Dockerfile").read_text()
    assert re.search(r"^USER app$", text, re.M)
    assert not re.search(r"^(ENV|ARG)\s+\w*(SECRET|PEPPER|PASSWORD|TOKEN)", text, re.M)
    assert "requirements.txt" in text and "==" in (DEPLOY / "requirements.txt").read_text()


def test_proxy_limits_body_size_and_hides_internal_endpoints():
    text = (DEPLOY / "Caddyfile").read_text()
    assert "max_size" in text and "/metrics" in text and "respond @internal 404" in text


def test_every_alert_points_to_a_runbook_section_that_exists():
    headings = {re.sub(r"[^a-z0-9]+", "-", h.lower()).strip("-") for h in re.findall(r"^## (.+)$", (ROOT / "docs" / "runbook.md").read_text(), re.M)}
    rules = [r for g in yaml.safe_load((DEPLOY / "alerts.yml").read_text())["groups"] for r in g["rules"]]
    assert rules
    for r in rules:
        assert r["annotations"]["runbook"].split("#")[1] in headings, r["alert"]


def test_system_card_has_the_sections_a_reviewer_needs():
    text = (ROOT / "docs" / "system_card.md").read_text()
    for h in ("Mục đích", "Giới hạn đã biết", "Dữ liệu và quyền riêng tư", "Chi phí và hạn mức"):
        assert h in text
