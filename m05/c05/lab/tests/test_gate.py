import json

import yaml

import gate


def make(passed_by_category):
    results = []
    for category, flags in passed_by_category.items():
        for i, flag in enumerate(flags):
            results.append({"id": f"{category}-{i}", "category": category, "passed": flag})
    return results


BASE = make({"status": [True] * 6, "refund": [True] * 6, "address": [True] * 5 + [False], "fee": [True] * 5 + [False]})


def test_pass_rate_and_categories():
    assert abs(gate.pass_rate(BASE) - 22 / 24) < 1e-9
    cats = gate.by_category(BASE)
    assert cats["status"] == 1.0
    assert abs(cats["address"] - 5 / 6) < 1e-9


def test_same_results_pass():
    assert gate.decide(BASE, BASE) == {"ok": True, "reasons": []}


def test_overall_drop_blocks():
    cand = make({"status": [True] * 6, "refund": [True] * 3 + [False] * 3, "address": [True] * 5 + [False], "fee": [True] * 4 + [False] * 2})
    result = gate.decide(BASE, cand)
    assert not result["ok"]
    assert any(r.startswith("overall_drop") for r in result["reasons"])


def test_category_drop_blocks_even_when_overall_is_fine():
    cand = make({"status": [True] * 6, "refund": [True] * 3 + [False] * 3, "address": [True] * 6, "fee": [True] * 6})
    assert abs(gate.pass_rate(BASE) - gate.pass_rate(cand)) < 0.05
    result = gate.decide(BASE, cand)
    assert not result["ok"]
    assert result["reasons"] == ["category_drop:refund: 0.500 > 0.17"]


def test_one_case_in_a_category_is_tolerated():
    cand = make({"status": [True] * 6, "refund": [True] * 5 + [False], "address": [True] * 5 + [False], "fee": [True] * 5 + [False]})
    assert gate.decide(BASE, cand, max_drop=0.1)["ok"]


def test_too_few_cases_blocks():
    small = BASE[:10]
    result = gate.decide(small, small)
    assert not result["ok"]
    assert result["reasons"][0].startswith("too_few_cases")


GOOD = """
jobs:
  eval-gate:
    steps:
      - run: python gate.py
  deploy:
    needs: [eval-gate]
    if: github.ref == 'refs/heads/main'
    steps:
      - run: ./deploy.sh
        env:
          KEY: ${{ secrets.KEY }}
"""

BAD = """
jobs:
  eval-gate:
    steps:
      - run: python gate.py
        continue-on-error: true
  deploy:
    needs: [build]
    steps:
      - run: echo ${{ secrets.KEY }} > key
"""


def test_good_workflow_has_no_problems():
    assert gate.check_workflow(yaml.safe_load(GOOD)) == []


def test_bad_workflow_reports_every_problem():
    problems = gate.check_workflow(yaml.safe_load(BAD))
    assert set(problems) == {"deploy_not_after_gate", "gate_continue_on_error", "deploy_not_main_only", "secret_in_run"}


def test_missing_job():
    assert gate.check_workflow({"jobs": {"test": {}}}) == ["missing_job"]


def test_cli_exit_codes(tmp_path, capsys):
    base, good, bad = tmp_path / "b.json", tmp_path / "g.json", tmp_path / "x.json"
    base.write_text(json.dumps(BASE))
    good.write_text(json.dumps(BASE))
    worse = make({"status": [True] * 6, "refund": [False] * 6, "address": [True] * 5 + [False], "fee": [True] * 5 + [False]})
    bad.write_text(json.dumps(worse))
    assert gate.main([str(base), str(good)]) == 0
    assert gate.main([str(base), str(bad)]) == 1
    out = capsys.readouterr().out
    assert "PASS" in out and "BLOCK" in out and "category_drop:refund" in out
