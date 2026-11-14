from collections import Counter

from common import percentile
from workload import FEATURE_SPEC, generate, read_jsonl, sources, write_jsonl


def test_same_seed_same_requests():
    a = generate(300)
    b = generate(300)
    assert [r.as_dict() for r in a] == [r.as_dict() for r in b]


def test_different_seed_differs():
    assert generate(50, seed=1)[0].as_dict() != generate(50, seed=2)[0].as_dict()


def test_sorted_by_arrival_and_unique_ids():
    rs = generate(400)
    assert [r.arrival_s for r in rs] == sorted(r.arrival_s for r in rs)
    assert len({r.request_id for r in rs}) == 400


def test_mix_close_to_spec():
    c = Counter(r.feature for r in generate(3000))
    assert abs(c["chat"] / 3000 - 0.70) < 0.04
    assert abs(c["knowledge_assistant"] / 3000 - 0.27) < 0.04
    assert 0.01 < c["weekly_report_agent"] / 3000 < 0.06


def test_long_tail_of_output_tokens():
    rs = [r for r in generate(3000) if r.feature == "chat"]
    out = [r.output_tokens for r in rs]
    assert percentile(out, 99) > 4 * percentile(out, 50)
    assert max(out) <= FEATURE_SPEC["chat"]["out_cap"]


def test_features_have_distinct_sizes():
    rs = generate(2000)
    med = {f: percentile([r.prompt_tokens for r in rs if r.feature == f], 50) for f in FEATURE_SPEC}
    assert med["chat"] < med["knowledge_assistant"] < med["weekly_report_agent"]


def test_report_only_for_tenants_and_roles_that_may_use_it():
    for r in generate(2000):
        if r.feature == "weekly_report_agent":
            assert r.tenant_id != "br-ben-song"
            assert r.role == "branch_manager"


def test_tiers_follow_feature():
    for r in generate(500):
        if r.feature == "weekly_report_agent":
            assert r.model == "fake-large"
        if r.feature == "chat":
            assert r.model in ("fake-small", "fake-medium")


def test_prompts_reuse_frozen_texts():
    src = sources()
    assert len(src["messages"]) == 300 and len(src["questions"]) > 50 and len(src["chunks"]) > 10 and len(src["cases"]) == 300
    rs = [r for r in generate(200) if r.feature == "chat"]
    assert rs[0].messages[-1]["content"] in src["messages"]


def test_jsonl_roundtrip(tmp_path):
    rs = generate(20)
    p = tmp_path / "w.jsonl"
    write_jsonl(rs, p)
    assert [r.as_dict() for r in read_jsonl(p)] == [r.as_dict() for r in rs]
