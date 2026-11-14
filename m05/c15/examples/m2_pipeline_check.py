import yaml

import _kit

D = _kit.PROJECT / "deploy"
wf = yaml.safe_load((D / "ci.yml").read_text())
jobs = wf["jobs"]
print("pipeline order:")
for name, job in jobs.items():
    print(f"  {name:10} needs={job.get('needs', '-'):10} if={job.get('if', 'always')}")
compose = yaml.safe_load((D / "compose.yaml").read_text())
print("\nservices:", ", ".join(compose["services"]))
print("published ports:")
for name, svc in compose["services"].items():
    for port in svc.get("ports", []):
        print(f"  {name:20} {port}")
env = compose["services"]["api"]["environment"]
print("\nsecrets in api environment:")
for k in ("JWT_SECRET", "KEY_PEPPER", "DEMO_PASSWORD"):
    print(f"  {k} = {env[k]}")
