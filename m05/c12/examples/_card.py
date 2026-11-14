import csv
import hashlib
import json
import sys
from pathlib import Path

M05 = Path(__file__).resolve().parents[2]
LAB = M05.parent
sys.path.insert(0, str(M05 / "platform"))
from workload import generate  # noqa: E402
from _release import run_canary  # noqa: E402

SECTIONS = ["identity", "intended_use", "out_of_scope", "models", "data_sources", "evaluation", "limitations", "oversight", "change_log", "config_digest"]
VAGUE = ("none", "n/a", "khong co", "không có", "tbd", "updating")
LABELS = ("Đã chạy", "Minh họa")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def config_digest(base=None):
    base = base or M05 / "data"
    return {name: sha(base / name)[:16] for name in ("tenants.json", "prices.json")}


def rows(path):
    with open(path, encoding="utf-8") as f:
        return max(0, sum(1 for _ in f) - 1)


def chat_cost_per_1000(prices):
    m = prices["models"]["fake-medium"]
    chat = [r for r in generate(3000, seed=42) if r.feature == "chat"][:1000]
    usd = sum(r.prompt_tokens * m["input_per_mtok"] + r.output_tokens * m["output_per_mtok"] for r in chat) / 1e6
    return round(usd, 3)


def stable_score():
    log, _ = run_canary("good")
    return round(sum(w[3] for w in log) / len(log), 3)


def build_card():
    tenants = json.loads((M05 / "data" / "tenants.json").read_text(encoding="utf-8"))
    prices = json.loads((M05 / "data" / "prices.json").read_text(encoding="utf-8"))
    no_report = [t["tenant_id"] for t in tenants["tenants"] if "weekly_report_agent" not in t["allowed_features"]]
    return {
        "identity": {"name": "Anh Ti AI Service", "version": "2026.11.0", "owner": "Ha (platform), approver: Lan", "date": "2026-11-14"},
        "intended_use": ["chat support for branch staff", "knowledge assistant on internal policy", "weekly report agent for branch managers"],
        "out_of_scope": ["decisions about hiring, pay or discipline of couriers", "legal or medical advice", "answers shown to end customers without a staff review"],
        "models": [{"tier": t, "model": m, "role": "illustrative alias, replace with a real model before launch"} for t, m in prices["tiers"].items()],
        "data_sources": [
            {"name": "tenants.json", "origin": "invented for teaching", "owner": "platform team", "license": "course material", "pii": False, "rows": len(tenants["tenants"])},
            {"name": "messages.csv", "origin": "synthetic support messages (m02)", "owner": "course authors", "license": "course material", "pii": False, "rows": rows(LAB / "m02" / "data" / "messages.csv")},
            {"name": "questions.csv", "origin": "synthetic questions (m03)", "owner": "course authors", "license": "course material", "pii": False, "rows": rows(LAB / "m03" / "data" / "questions.csv")},
            {"name": "cases.csv", "origin": "synthetic complaint cases (m04)", "owner": "course authors", "license": "course material", "pii": False, "rows": rows(LAB / "m04" / "data" / "cases.csv")},
        ],
        "evaluation": [
            {"metric": "online answer score, stable prompt v1", "value": stable_score(), "dataset": "scripted traffic, seed 7, 8 windows of 400 requests", "label": "Minh họa"},
            {"metric": "cost per 1000 chat requests, medium tier", "value": chat_cost_per_1000(prices), "dataset": "1000 chat requests from workload.generate(seed=42), prices.json", "label": "Minh họa"},
        ],
        "limitations": [
            "A small model can state a wrong delivery policy with confidence; staff must check refund and compensation answers.",
            f"Weekly report agent is off for {', '.join(no_report)}; the other tenants have it.",
            "Log redaction covers phone numbers and addresses, not personal names.",
            "Vietnamese only; other languages were not evaluated.",
        ],
        "oversight": {"owner": "platform team", "escalation": "oncall channel, response within 30 minutes in office hours", "human_review": "refund and compensation answers"},
        "change_log": [{"version": "2026.11.0", "date": "2026-11-14", "change": "first card", "approved_by": "Lan"}],
        "config_digest": config_digest(),
    }


def lint_card(card, current_digest=None):
    issues = []
    for s in SECTIONS:
        if s not in card or card[s] in (None, "", [], {}):
            issues.append(f"missing section: {s}")
    for i, lim in enumerate(card.get("limitations", [])):
        if lim.strip().lower() in VAGUE or len(lim.split()) < 5:
            issues.append(f"limitation {i + 1} is too vague: {lim!r}")
    if len(card.get("limitations", [])) < 3:
        issues.append("fewer than 3 limitations")
    for ev in card.get("evaluation", []):
        if not ev.get("dataset"):
            issues.append(f"evaluation without dataset: {ev.get('metric')}")
        if ev.get("label") not in LABELS:
            issues.append(f"evaluation without honest label: {ev.get('metric')}")
    for ds in card.get("data_sources", []):
        for k in ("origin", "owner", "license", "pii"):
            if k not in ds:
                issues.append(f"data source {ds.get('name')} lacks {k}")
    if current_digest is not None and card.get("config_digest") != current_digest:
        changed = [k for k in current_digest if card.get("config_digest", {}).get(k) != current_digest[k]]
        issues.append(f"card is stale, changed files: {', '.join(changed)}")
    return issues


def render(card):
    out = [f"# {card['identity']['name']} v{card['identity']['version']} ({card['identity']['date']})", ""]
    out.append("Intended use: " + "; ".join(card["intended_use"]))
    out.append("Out of scope: " + "; ".join(card["out_of_scope"]))
    out.append("Models: " + ", ".join(f"{m['tier']}={m['model']}" for m in card["models"]))
    out.append("Data sources:")
    out += [f"  - {d['name']}: {d['origin']}, {d['rows']} rows, pii={d['pii']}" for d in card["data_sources"]]
    out.append("Evaluation:")
    out += [f"  - {e['metric']} = {e['value']} on {e['dataset']} [{e['label']}]" for e in card["evaluation"]]
    out.append("Limitations:")
    out += [f"  - {x}" for x in card["limitations"]]
    return "\n".join(out)
