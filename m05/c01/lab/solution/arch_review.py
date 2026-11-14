import re
import sys
from pathlib import Path

REQUIRED_NODES = ["User", "Caddy", "API", "Gateway", "Worker", "PostgreSQL", "Redis", "Provider", "Observability"]
SECTIONS = ["status", "context", "options", "decision", "consequences"]
MODES = ("sync", "streaming", "job")

NODE_DEF = re.compile(r'(\w+)(?:\[\(|\[|\(\(|\(|\{)"([^"]*)"(?:\)\]|\]|\)\)|\)|\})')
EDGE = re.compile(r"(\w+)\s*(?:-->|-\.->|==>)\s*(?:\|([^|]*)\|\s*)?(\w+)")


def parse_containers(text):
    """Return (nodes, edges): nodes maps id to label, edges is a list of (source, target, label)."""
    nodes, edges = {}, []
    for raw in text.splitlines():
        line = raw.split("%%")[0]
        for m in NODE_DEF.finditer(line):
            nodes[m.group(1)] = m.group(2)
        plain = re.sub(r":::\w+", "", NODE_DEF.sub(lambda m: m.group(1), line))
        for m in EDGE.finditer(plain):
            src, label, dst = m.group(1), (m.group(2) or "").strip(), m.group(3)
            edges.append((src, dst, label))
            nodes.setdefault(src, src)
            nodes.setdefault(dst, dst)
    return nodes, edges


def check_architecture(text):
    """Return a sorted list of problems; an empty list means the diagram follows the course rules."""
    nodes, edges = parse_containers(text)
    problems = []
    for name in REQUIRED_NODES:
        if name not in nodes:
            problems.append(f"missing node {name}")
    pairs = {(a, b) for a, b, _ in edges}
    for a, b, label in edges:
        if not label:
            problems.append(f"edge {a} to {b} has no label")
        if "Provider" in (a, b) and a != "Gateway" and b == "Provider":
            problems.append(f"{a} calls Provider directly: every model call goes through Gateway")
    if ("API", "Worker") in pairs or ("Worker", "API") in pairs:
        problems.append("API and Worker talk directly: put the job in Redis or PostgreSQL")
    if not (("API", "Redis") in pairs or ("API", "PostgreSQL") in pairs):
        problems.append("API never enqueues a job: add an edge from API to Redis or PostgreSQL")
    if ("Redis", "Worker") not in pairs and ("Worker", "Redis") not in pairs:
        problems.append("Worker has no edge with Redis (the job queue)")
    if ("Worker", "Gateway") not in pairs:
        problems.append("Worker must call Gateway, not Provider")
    if ("Gateway", "PostgreSQL") not in pairs:
        problems.append("Gateway has no edge to PostgreSQL for usage records")
    if ("Caddy", "API") not in pairs:
        problems.append("missing edge Caddy to API")
    if ("User", "Caddy") not in pairs:
        problems.append("missing edge User to Caddy")
    reporters = {a for a, b, _ in edges if b == "Observability"}
    if len(reporters & {"API", "Gateway", "Worker"}) < 3:
        problems.append("API, Gateway and Worker must all report to Observability")
    return sorted(set(problems))


def parse_adr(text):
    """Return {'title': ..., 'status': ..., 'context': ..., ...} with lower-case section names."""
    out = {"title": ""}
    for line in text.splitlines():
        if line.startswith("# "):
            out["title"] = line[2:].strip()
            break
    parts = re.split(r"^## +(.+?) *$", text, flags=re.M)
    for i in range(1, len(parts) - 1, 2):
        out[parts[i].strip().lower()] = parts[i + 1].strip()
    return out


def adr_mode(adr):
    """The mode named on the first line of the Decision section, or None."""
    first = (adr.get("decision") or "").strip().splitlines()[:1]
    found = [m for m in MODES if first and m in first[0].lower()]
    return found[0] if len(found) == 1 else None


def check_adr(text):
    adr = parse_adr(text)
    problems = []
    if not adr["title"].startswith("ADR-"):
        problems.append("title must start with 'ADR-'")
    for s in SECTIONS:
        if not adr.get(s):
            problems.append(f"missing section {s}")
    if adr.get("status") and adr["status"].split()[0].strip(".") not in ("Proposed", "Accepted", "Superseded"):
        problems.append("status must be Proposed, Accepted or Superseded")
    if len(re.findall(r"\d+", adr.get("context", ""))) < 2:
        problems.append("context needs at least two numbers (duration, volume, timeout)")
    options = (adr.get("options") or "").lower()
    if not all(m in options for m in MODES):
        problems.append("options must discuss sync, streaming and job")
    if adr.get("decision") and adr_mode(adr) is None:
        problems.append("first line of decision must name exactly one of sync, streaming, job")
    if len([x for x in (adr.get("consequences") or "").splitlines() if x.strip().startswith("- ")]) < 2:
        problems.append("consequences needs at least two bullet lines")
    return problems


def choose_mode(p95_seconds, user_waiting, partial_useful, proxy_timeout_s=60):
    """sync, streaming or job from the 95th percentile duration and who is waiting."""
    if not user_waiting:
        return "job"
    if p95_seconds >= proxy_timeout_s * 0.5:
        return "job"
    if p95_seconds <= 2:
        return "sync"
    return "streaming" if partial_useful else "sync"


def audit(folder):
    folder = Path(folder)
    report = {}
    arch = folder / "architecture.mmd"
    report["architecture.mmd"] = check_architecture(arch.read_text(encoding="utf-8")) if arch.exists() else ["file not found"]
    for f in sorted(folder.glob("adr-*.md")):
        report[f.name] = check_adr(f.read_text(encoding="utf-8"))
    return report


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "deliverables"
    result = audit(folder)
    for name, problems in result.items():
        print(f"{name:<32}", "ok" if not problems else f"{len(problems)} problem(s)")
        for p in problems:
            print("   -", p)
    modes = {f.name: adr_mode(parse_adr(f.read_text(encoding="utf-8"))) for f in sorted(Path(folder).glob("adr-*.md"))}
    print("decisions:", modes)
    sys.exit(1 if any(result.values()) else 0)
