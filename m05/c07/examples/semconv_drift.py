import importlib.metadata as md
import json

from opentelemetry.semconv._incubating.attributes import gen_ai_attributes as g

from _support import DATA

snap = json.loads((DATA / "genai_semconv_snapshot.json").read_text(encoding="utf-8"))
package = {getattr(g, n) for n in dir(g) if n.startswith("GEN_AI_") and isinstance(getattr(g, n), str)}
spec = set(snap["gen_ai_attributes"])

print(f"opentelemetry-semantic-conventions {md.version('opentelemetry-semantic-conventions')}: {len(package)} gen_ai names")
print(f"GenAI spec snapshot ({snap['read_on']}, commit {snap['commit']}): {len(spec)} gen_ai names, status {snap['status'].split(' ')[0]}")
print("in the package but not in the spec:")
for n in sorted(package - spec):
    print("  ", n, "| replacement:", snap["older_names"].get(n, "none listed"))
print("in the spec but not in the package:", len(spec - package))
print("examples:", ", ".join(sorted(spec - package)[:4]))
