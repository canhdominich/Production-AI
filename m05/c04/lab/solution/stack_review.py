import re
import sys
from pathlib import Path

import yaml

DEP_FILES = ("pyproject.toml", "uv.lock", "requirements")
INSTALL = re.compile(r"\b(uv sync|uv pip install|pip install)\b")
SECRET_KEYS = ("PASSWORD", "SECRET", "TOKEN", "API_KEY")
DEFAULT_PORTS = {"5432", "6379", "8000", "8080"}


def parse_dockerfile(text):
    logical, buf = [], ""
    for raw in text.splitlines():
        line = raw.strip()
        if not buf and (not line or line.startswith("#")):
            continue
        if line.endswith("\\"):
            buf += line[:-1] + " "
            continue
        logical.append((buf + line).strip())
        buf = ""
    stages = []
    for line in logical:
        cmd, _, rest = line.partition(" ")
        cmd = cmd.upper()
        if cmd == "FROM":
            m = re.match(r"(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?", rest.strip(), flags=re.I)
            stages.append({"base": m.group(1), "name": (m.group(2) or "").lower(), "instructions": []})
        elif stages:
            stages[-1]["instructions"].append((cmd, rest.strip()))
    return stages


def _is_dep_copy(args):
    parts = [p for p in args.split() if not p.startswith("--")]
    sources = parts[:-1]
    return bool(sources) and all(any(d in s for d in DEP_FILES) for s in sources)


def check_dockerfile(text):
    errs = set()
    stages = parse_dockerfile(text)
    if len(stages) < 2:
        errs.add("single stage: build tools stay in the final image, use a builder stage")
    names = {s["name"] for s in stages if s["name"]}
    for s in stages:
        base = s["base"]
        if base.lower() in names or base == "scratch":
            continue
        if ":" not in base.split("/")[-1] or base.endswith(":latest"):
            errs.add(f"base image not pinned to a tag: {base}")
    for s in stages:
        label = s["name"] or s["base"]
        seen_code_copy = False
        for cmd, args in s["instructions"]:
            if cmd in ("COPY", "ADD") and "--from=" not in args and not _is_dep_copy(args):
                seen_code_copy = True
            if cmd == "RUN" and INSTALL.search(args) and seen_code_copy:
                errs.add(f"stage {label}: application code copied before dependencies are installed, cache is lost on every edit")
                break
    if stages:
        users = [a for c, a in stages[-1]["instructions"] if c == "USER"]
        if not users or users[-1].split(":")[0] in ("root", "0"):
            errs.add("final stage runs as root, add a non-root USER")
    return sorted(errs)


def parse_compose(text):
    data = yaml.safe_load(text) or {}
    services = {}
    for name, svc in (data.get("services") or {}).items():
        dep = svc.get("depends_on") or {}
        if isinstance(dep, list):
            dep = {d: "service_started" for d in dep}
        else:
            dep = {k: (v or {}).get("condition", "service_started") for k, v in dep.items()}
        services[name] = {
            "image": svc.get("image", ""),
            "build": bool(svc.get("build")),
            "ports": [str(p) for p in svc.get("ports") or []],
            "healthcheck": bool(svc.get("healthcheck")),
            "depends_on": dep,
            "volumes": [str(v) for v in svc.get("volumes") or []],
            "restart": str(svc.get("restart", "")),
            "environment": svc.get("environment") or {},
        }
    return {"services": services, "volumes": list((data.get("volumes") or {}).keys())}


def check_compose(text):
    cfg = parse_compose(text)
    svcs = cfg["services"]
    errs = set()
    for name, s in svcs.items():
        oneshot = s["restart"] == "no"
        if not oneshot and not s["healthcheck"]:
            errs.add(f"{name}: long-running service has no healthcheck")
        for dep, cond in s["depends_on"].items():
            target = svcs.get(dep)
            if not target:
                errs.add(f"{name}: depends_on unknown service {dep}")
                continue
            want = "service_completed_successfully" if target["restart"] == "no" and not target["healthcheck"] else "service_healthy"
            if cond != want:
                errs.add(f"{name}: depends_on {dep} needs condition {want}, found {cond}")
        image = s["image"]
        if image and not s["build"] and (":" not in image.split("/")[-1] or image.endswith(":latest")):
            errs.add(f"{name}: image not pinned to a tag: {image}")
        for p in s["ports"]:
            parts = p.split(":")
            if len(parts) < 3 or parts[0] != "127.0.0.1":
                errs.add(f"{name}: published port {p} is not bound to 127.0.0.1")
            elif parts[1] in DEFAULT_PORTS:
                errs.add(f"{name}: host port {parts[1]} is a default port, use a project port")
        if "postgres" in image or "pgvector" in image:
            named = [v for v in s["volumes"] if v.split(":")[0] in cfg["volumes"] and v.split(":")[1].startswith("/var/lib/postgresql")]
            if not named:
                errs.add(f"{name}: database data is not on a named volume")
        env = s["environment"]
        pairs = env.items() if isinstance(env, dict) else [e.split("=", 1) for e in env if "=" in e]
        for k, v in pairs:
            if any(w in str(k).upper() for w in SECRET_KEYS) and "${" not in str(v):
                errs.add(f"{name}: secret {k} written in the file, read it from the environment")
    return sorted(errs)


def weights_strategy(size_mb, hosts=1, air_gapped=False):
    if air_gapped or size_mb < 150:
        return "bake"
    if hosts <= 1:
        return "volume"
    return "mirror"


def review(root):
    root = Path(root)
    report = []
    df, cf = root / "Dockerfile", root / "compose.yaml"
    for label, path, fn in (("Dockerfile", df, check_dockerfile), ("compose.yaml", cf, check_compose)):
        errs = fn(path.read_text(encoding="utf-8")) if path.exists() else [f"{label} missing"]
        report.append(f"{label}: {'ok' if not errs else str(len(errs)) + ' problem(s)'}")
        report += [f"  - {e}" for e in errs]
    return report


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    lines = review(target)
    print("\n".join(lines))
    sys.exit(0 if all("problem" not in x and "missing" not in x for x in lines) else 1)
