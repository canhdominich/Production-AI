import re

from _kit import PriceTable, generate
from common import estimate_tokens
from workload import SYSTEM, sources

prices = PriceTable()
MODEL = "fake-small"
ANSWER = 120
src = sources()
user_tokens = sum(estimate_tokens(m) + 4 for m in src["messages"]) / len(src["messages"])
system_tokens = estimate_tokens(SYSTEM["chat"]) + 4


def conversation_cost(turns, model=MODEL, cache_history=False):
    total, history = 0.0, 0
    for _ in range(turns):
        prompt = system_tokens + history + user_tokens
        cached = round(system_tokens + history) if cache_history else 0
        total += prices.cost(model, prompt, ANSWER, cached_tokens=cached)
        history += user_tokens + ANSWER
    return total


print(f"chat on {MODEL}: system {system_tokens} tokens, user message {user_tokens:.0f}, answer {ANSWER}")
first = conversation_cost(1)
print(f"{'turns':>5} {'cost per conversation':>22} {'naive turns x first':>20} {'underestimate':>14} {'history cached':>15}")
for t in (1, 3, 5, 8, 12):
    c = conversation_cost(t)
    print(f"{t:5d} {'$' + format(c, '.6f'):>22} {'$' + format(first * t, '.6f'):>20} {1 - first * t / c:13.0%} {'$' + format(conversation_cost(t, cache_history=True), '.6f'):>15}")

weekly = [r for r in generate(6000, seed=42) if r.feature == "weekly_report_agent"]
cases = [int(re.search(r"\((\d+) ca\)", r.messages[1]["content"]).group(1)) for r in weekly]
one, four = 0.0, 0.0
for r in weekly:
    one += prices.cost(r.model, r.prompt_tokens, r.output_tokens)
    step_out = r.output_tokens / r.steps
    for s in range(r.steps):
        four += prices.cost(r.model, r.prompt_tokens + s * step_out, step_out)
n = len(weekly)
print(f"\nweekly report agent on {weekly[0].model}: {n} reports, {sum(cases)} complaints in total")
print(f"  as one call   ${one / n:.4f} per report, ${one / sum(cases):.5f} per complaint")
print(f"  as 4 steps    ${four / n:.4f} per report, ${four / sum(cases):.5f} per complaint (each step resends the prompt)")
print(f"  4 steps cost {four / one:.2f} times the single call")
