import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "platform"))
from workload import generate

SLOTS = 8
STEP_MS = 20
lengths = [min(r.output_tokens, 400) for r in generate(400, seed=42) if r.feature == "chat"][:64]


def static(lens):
    steps = busy = 0
    done = []
    for i in range(0, len(lens), SLOTS):
        batch = lens[i:i + SLOTS]
        longest = max(batch)
        for n in batch:
            done.append(steps + n)
        steps += longest
        busy += sum(batch)
    return steps, busy, done


def continuous(lens):
    queue, active, steps, busy, done = list(lens), [], 0, 0, []
    while queue or active:
        while queue and len(active) < SLOTS:
            active.append(queue.pop(0))
        steps += 1
        busy += len(active)
        active = [a - 1 for a in active]
        for a in active:
            if a == 0:
                done.append(steps)
        active = [a for a in active if a > 0]
    return steps, busy, done


print(f"{len(lengths)} chat requests, output tokens: median {sorted(lengths)[len(lengths)//2]}, max {max(lengths)}, {SLOTS} slots, one step = {STEP_MS} ms [Minh hoa]")
print("policy       steps  slot use   tokens/s   mean finish   p95 finish")
for name, fn in (("static", static), ("continuous", continuous)):
    steps, busy, done = fn(lengths)
    done = sorted(done)
    print(f"{name:<11} {steps:>6}   {100*busy/(steps*SLOTS):5.1f}%   {busy/(steps*STEP_MS/1000):8.1f}   {sum(done)/len(done)*STEP_MS/1000:9.2f} s   {done[int(0.95*len(done))]*STEP_MS/1000:8.2f} s")
