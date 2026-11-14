from pathlib import Path

import pytest

import arch_review as ar

HERE = Path(__file__).resolve().parents[1]

NODES = [
    'User["User: branch staff"]', 'Caddy["Caddy: HTTPS"]', 'API["API: auth, streaming"]', 'Gateway["Gateway: limits, usage"]',
    'Worker["Worker: jobs"]', 'Redis[("Redis: queue")]', 'PostgreSQL[("PostgreSQL: usage, jobs")]', 'Provider["Provider: model API"]',
    'Observability["Observability"]',
]
EDGES = [
    ("User", "Caddy", "HTTPS"), ("Caddy", "API", "proxy"), ("API", "Gateway", "chat call"), ("API", "Redis", "enqueue job"),
    ("Redis", "Worker", "job id"), ("Worker", "Gateway", "model calls"), ("Gateway", "Provider", "model request"),
    ("Gateway", "PostgreSQL", "usage rows"), ("API", "Observability", "traces"), ("Gateway", "Observability", "metrics"),
    ("Worker", "Observability", "traces"),
]


def diagram(drop_edges=(), add_edges=(), drop_nodes=(), unlabeled=()):
    lines = ["flowchart TD"] + ["    " + n for n in NODES if n.split("[")[0] not in drop_nodes]
    for a, b, label in [e for e in EDGES if e[:2] not in drop_edges] + list(add_edges):
        lines.append(f"    {a} -->|{label}| {b}" if (a, b) not in unlabeled else f"    {a} --> {b}")
    lines.append("    class API,Gateway main")
    return "\n".join(lines) + "\n"


def adr(mode="job", status="Accepted", context="Báo cáo mất 56 giây, timeout 60 giây.", options=None, bullets=2):
    options = options if options is not None else "- sync: chờ cả câu.\n- streaming: gửi từng chữ.\n- job: hàng đợi."
    cons = "\n".join(f"- Hệ quả số {i + 1}." for i in range(bullets))
    return f"# ADR-003: Báo cáo tuần\n\n## Status\n\n{status}\n\n## Context\n\n{context}\n\n## Options\n\n{options}\n\n## Decision\n\n{mode}. Lý do ngắn.\n\n## Consequences\n\n{cons}\n"


SMALL = '''flowchart TD
    A["Alpha: first"]
    B[("Beta: store")]
    C(("Gamma"))
    A -->|calls| B
    B --> C:::x
    A -- not an edge
    %% A -->|hidden| C
'''


def test_parse_nodes_and_labels():
    nodes, _ = ar.parse_containers(SMALL)
    assert nodes == {"A": "Alpha: first", "B": "Beta: store", "C": "Gamma"}


def test_parse_edges_with_and_without_label_and_ignores_comments():
    _, edges = ar.parse_containers(SMALL)
    assert edges == [("A", "B", "calls"), ("B", "C", "")]


def test_parse_edge_only_nodes_get_id_as_label():
    nodes, edges = ar.parse_containers("flowchart TD\n    X -->|go| Y\n")
    assert nodes == {"X": "X", "Y": "Y"} and edges == [("X", "Y", "go")]


def test_parse_full_diagram_has_all_nodes_and_edges():
    nodes, edges = ar.parse_containers(diagram())
    assert set(nodes) == set(ar.REQUIRED_NODES)
    assert len(edges) == len(EDGES)


def test_clean_architecture_has_no_problems():
    assert ar.check_architecture(diagram()) == []


def test_missing_node_reported():
    problems = ar.check_architecture(diagram(drop_nodes=("Redis",), drop_edges=(("API", "Redis"), ("Redis", "Worker"))))
    assert "missing node Redis" in problems


def test_api_calling_provider_directly_reported():
    assert any("API calls Provider directly" in p for p in ar.check_architecture(diagram(add_edges=[("API", "Provider", "shortcut")])))


def test_worker_calling_provider_directly_reported():
    problems = ar.check_architecture(diagram(drop_edges=(("Worker", "Gateway"),), add_edges=[("Worker", "Provider", "model calls")]))
    assert any("Worker calls Provider directly" in p for p in problems)
    assert any("Worker must call Gateway" in p for p in problems)


def test_unlabeled_edge_reported():
    assert "edge Caddy to API has no label" in ar.check_architecture(diagram(unlabeled=(("Caddy", "API"),)))


def test_api_to_worker_shortcut_reported():
    assert any("API and Worker talk directly" in p for p in ar.check_architecture(diagram(add_edges=[("API", "Worker", "run now")])))


def test_job_never_enqueued_reported():
    problems = ar.check_architecture(diagram(drop_edges=(("API", "Redis"),)))
    assert any("never enqueues" in p for p in problems)


def test_observability_needs_three_reporters():
    assert any("must all report to Observability" in p for p in ar.check_architecture(diagram(drop_edges=(("Worker", "Observability"),))))


def test_gateway_must_write_usage():
    assert any("usage records" in p for p in ar.check_architecture(diagram(drop_edges=(("Gateway", "PostgreSQL"),))))


def test_parse_adr_sections():
    parsed = ar.parse_adr(adr())
    assert parsed["title"] == "ADR-003: Báo cáo tuần"
    assert parsed["status"] == "Accepted"
    assert parsed["decision"].startswith("job.")
    assert set(ar.SECTIONS) <= set(parsed)


def test_adr_mode_reads_first_line_of_decision():
    assert ar.adr_mode(ar.parse_adr(adr(mode="streaming"))) == "streaming"
    assert ar.adr_mode(ar.parse_adr(adr(mode="sync hoặc job"))) is None


def test_clean_adr_has_no_problems():
    assert ar.check_adr(adr()) == []


def test_adr_missing_section_and_bad_status():
    text = adr(status="Maybe").replace("## Consequences", "## Notes")
    problems = ar.check_adr(text)
    assert "missing section consequences" in problems
    assert "status must be Proposed, Accepted or Superseded" in problems


def test_adr_context_needs_numbers_and_decision_one_mode():
    problems = ar.check_adr(adr(mode="sync hoặc job", context="Chạy lâu."))
    assert any("two numbers" in p for p in problems)
    assert any("exactly one of" in p for p in problems)


def test_adr_options_must_cover_all_modes_and_consequences_need_bullets():
    problems = ar.check_adr(adr(options="- sync: chờ.\n- job: nền.", bullets=1))
    assert any("options must discuss" in p for p in problems)
    assert any("two bullet lines" in p for p in problems)


@pytest.mark.parametrize("p95,waiting,partial,expected", [
    (1.2, True, False, "sync"),
    (7.7, True, True, "streaming"),
    (9.0, True, False, "sync"),
    (17.8, True, True, "streaming"),
    (29.9, True, True, "streaming"),
    (30.0, True, True, "job"),
    (109.0, True, True, "job"),
    (3.0, False, True, "job"),
])
def test_choose_mode(p95, waiting, partial, expected):
    assert ar.choose_mode(p95, waiting, partial) == expected


def test_choose_mode_respects_custom_timeout():
    assert ar.choose_mode(12, True, True, proxy_timeout_s=20) == "job"
    assert ar.choose_mode(12, True, True, proxy_timeout_s=60) == "streaming"


def test_my_deliverables_pass_the_checker():
    folder = HERE / "deliverables"
    report = ar.audit(folder)
    assert "architecture.mmd" in report
    assert len([k for k in report if k.startswith("adr-")]) == 3
    assert all(not problems for problems in report.values()), report


def test_my_adr_decisions_match_the_measurements():
    folder = HERE / "deliverables"
    modes = {f.name[:7]: ar.adr_mode(ar.parse_adr(f.read_text(encoding="utf-8"))) for f in sorted(folder.glob("adr-*.md"))}
    assert modes == {"adr-001": "streaming", "adr-002": "streaming", "adr-003": "job"}
