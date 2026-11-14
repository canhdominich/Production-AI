import json
import re
import time

from _dock import compose

F = "variants/compose.race.yaml"
for attempt in range(1, 6):
    compose("down", "-v", "--remove-orphans", file=F)
    compose("up", "-d", "postgres", "migrate", file=F)
    time.sleep(4)
    rows = [json.loads(x) for x in compose("ps", "-a", "--format", "json", file=F).stdout.strip().splitlines() if x.startswith("{")] or json.loads(compose("ps", "-a", "--format", "json", file=F).stdout)
    code = next(r["ExitCode"] for r in rows if r["Service"] == "migrate")
    if code != 0:
        break
logs = compose("logs", "--no-color", "migrate", file=F).stdout.strip().splitlines()
print(f"attempt {attempt}: migrate container exit code {code}")
for line in logs[-2:]:
    print(re.sub(r"\d+\.\d+\.\d+\.\d+", "<ip>", line.split("|", 1)[1].strip())[:150])
compose("down", "-v", "--remove-orphans", file=F)
