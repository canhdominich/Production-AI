import copy
import re

import jsonschema

from _dashboard import PANELS, build, write
from _metrics import exposed_names
from _rules import RULES_DIR, promtool, recording_rules, write_yaml

SCHEMA = {
    "type": "object", "required": ["uid", "title", "schemaVersion", "panels"],
    "properties": {"schemaVersion": {"type": "integer", "minimum": 39}, "panels": {"type": "array", "minItems": 1, "items": {
        "type": "object", "required": ["id", "type", "title", "gridPos", "targets"],
        "properties": {
            "id": {"type": "integer"},
            "gridPos": {"type": "object", "required": ["h", "w", "x", "y"], "properties": {"w": {"type": "integer", "minimum": 1, "maximum": 24}, "x": {"type": "integer", "minimum": 0, "maximum": 23}}},
            "targets": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["expr", "refId"]}}}}}}}
KNOWN = exposed_names() | {r["record"] for r in recording_rules()}


def problems(dash):
    errs = [e.message for e in jsonschema.Draft202012Validator(SCHEMA).iter_errors(dash)]
    panels = dash["panels"]
    ids = [p["id"] for p in panels]
    errs += [f"duplicate panel id {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
    for i, a in enumerate(panels):
        for b in panels[i + 1:]:
            ga, gb = a["gridPos"], b["gridPos"]
            if ga["x"] < gb["x"] + gb["w"] and gb["x"] < ga["x"] + ga["w"] and ga["y"] < gb["y"] + gb["h"] and gb["y"] < ga["y"] + ga["h"]:
                errs.append(f"panels {a['id']} and {b['id']} overlap")
    for p in panels:
        for name in sorted({n for t in p.get("targets", []) for n in re.findall(r"\b(llm[a-z0-9_:]*)", t["expr"])}):
            if name not in KNOWN:
                errs.append(f"panel {p['id']} '{p['title']}' uses unknown metric {name}")
    return errs


def promql_errors(dash):
    doc = {"groups": [{"name": "dashboard-exprs", "rules": [{"record": f"dash:panel_{p['id']}", "expr": t["expr"]} for p in dash["panels"] for t in p["targets"]]}]}
    write_yaml(RULES_DIR / "_dashboard_exprs.yml", doc)
    code, out = promtool("check", "rules", "/rules/_dashboard_exprs.yml")
    (RULES_DIR / "_dashboard_exprs.yml").unlink()
    return code, out


dash = build()
write(dash)
print(f"dashboard '{dash['title']}': {len(dash['panels'])} panels, schemaVersion {dash['schemaVersion']}")
print("schema, layout and metric names:", problems(dash) or "no problems")
code, out = promql_errors(dash)
print("PromQL syntax through promtool:", " ".join(out.split()))

bad = copy.deepcopy(dash)
bad["panels"][2]["targets"][0]["expr"] = bad["panels"][2]["targets"][0]["expr"].replace("llm_request_duration_seconds_bucket", "llm_request_seconds_bucket")
bad["panels"][4]["id"] = 4
bad["panels"][5]["gridPos"]["x"] = 6
del bad["panels"][6]["targets"]
print("\nafter four slips (wrong metric name, duplicate id, panels overlap, panel without query):")
for e in problems(bad):
    print(" -", e)
