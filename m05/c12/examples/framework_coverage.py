from collections import defaultdict
from pathlib import Path

LAB = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

CONTROLS = [
    ("GOVERN", "Named owner and approver for each release", HERE / "_card.py"),
    ("GOVERN", "Policy: what the service must not be used for", HERE / "_card.py"),
    ("GOVERN", "Staff training on AI limits", None),
    ("MAP", "Intended use and out-of-scope list written down", HERE / "_card.py"),
    ("MAP", "Data sources with origin and owner", HERE / "data_provenance.py"),
    ("MAP", "Use case risk triage (EU AI Act tier)", HERE / "ai_act_triage.py"),
    ("MEASURE", "Online quality score per prompt version", HERE / "_release.py"),
    ("MEASURE", "Redaction leak test on logs", LAB / "c08" / "examples" / "naive_logging_leak.py"),
    ("MEASURE", "Fairness check across tenants", None),
    ("MANAGE", "Canary with automatic rollback", HERE / "canary_rollback.py"),
    ("MANAGE", "Release and rollback events recorded", HERE / "prompt_registry.py"),
    ("MANAGE", "Incident reporting process", None),
]

by_fn = defaultdict(list)
for fn, text, evidence in CONTROLS:
    by_fn[fn].append((text, evidence is not None and evidence.exists()))

for fn in ("GOVERN", "MAP", "MEASURE", "MANAGE"):
    items = by_fn[fn]
    done = sum(ok for _, ok in items)
    print(f"{fn:8s}{done}/{len(items)}")
    for text, ok in items:
        print(f"  [{'x' if ok else ' '}] {text}")
total = sum(ok for items in by_fn.values() for _, ok in items)
print(f"covered {total} of {len(CONTROLS)}; gaps are decisions to make, not files to create")
