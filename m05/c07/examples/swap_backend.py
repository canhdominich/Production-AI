from _genai import SNAPSHOT, read_spans
from _support import DATA

spans = [s for s in read_spans(DATA / "traces_demo.jsonl") if s["attributes"].get("gen_ai.operation.name") == "chat"]
NEW_TO_OLD = {new: old for old, new in SNAPSHOT["older_names"].items()}


def old_style(attrs):
    return {NEW_TO_OLD.get(k, k): v for k, v in attrs.items()}


def dashboard_tokens(attributes_list, input_key, output_key):
    rows = {}
    for a in attributes_list:
        t = rows.setdefault(a["anhti.tenant.id"], [0, 0])
        t[0] += a.get(input_key, 0)
        t[1] += a.get(output_key, 0)
    return rows


new = [s["attributes"] for s in spans]
old = [old_style(a) for a in new]
OLD_KEYS = ("gen_ai.usage.prompt_tokens", "gen_ai.usage.completion_tokens")
NEW_KEYS = ("gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens")


def aliased(a):
    return {**a, **{n: a[o] for o, n in SNAPSHOT["older_names"].items() if o in a}}


print("tokens per tenant (input, output)")
print("dashboard written for the older names, fed with older spans:   ", dashboard_tokens(old, *OLD_KEYS))
print("same dashboard, after the library switched to the current names:", dashboard_tokens(new, *OLD_KEYS))
print("dashboard with one alias step, fed with current spans:         ", dashboard_tokens([aliased(a) for a in new], *NEW_KEYS))
print("dashboard with one alias step, fed with older spans:           ", dashboard_tokens([aliased(a) for a in old], *NEW_KEYS))
