import _kit  # noqa: F401
from conftest import World, seed_spend

w = World()
budget = 150.0
print(f"tenant br-cau-go, monthly budget {budget:.0f} USD (illustrative prices), user cg-03 asks for tier large")
print(f"{'spent so far':>13}{'state':>7}{'status':>8}{'model used':>13}{'cost of call':>14}")
spent = 0.0
calls_before_block = 0
for target in (0.0, 0.5, 0.79, 0.81, 0.95, 0.999, 1.0):
    seed_spend(w.store, "br-cau-go", budget * target - spent)
    spent = budget * target
    before = w.primary.calls
    r = w.chat("cg-03", tier="large")
    if r.status_code == 200:
        b = r.json()
        spent += b["cost_usd"]
        print(f"{target * budget:>13.2f}{b['budget_state']:>7}{r.status_code:>8}{b['model']:>13}{b['cost_usd']:>14.6f}")
    else:
        calls_before_block = before
        print(f"{target * budget:>13.2f}{'hard':>7}{r.status_code:>8}{'-':>13}{'-':>14}  {r.json()['error']['code']}")
print("provider calls made by the blocked request:", w.primary.calls - calls_before_block)
print("other tenant still served:", w.chat("dp-02").status_code)
