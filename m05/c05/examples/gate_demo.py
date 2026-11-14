from _gate import by_category, decide, load_suite, pass_rate, run_eval

suite = load_suite()
base = run_eval(suite, "v1")
print(f"baseline v1: {sum(r['passed'] for r in base)}/{len(base)} = {pass_rate(base):.3f}")
print("  by category:", {c: round(v, 2) for c, v in by_category(base).items()})

for version in ("v2", "v3"):
    cand = run_eval(suite, version)
    result = decide(base, cand)
    print(f"\n{version} ({suite['versions'][version]['label']})")
    print(f"  {sum(r['passed'] for r in cand)}/{len(cand)} = {pass_rate(cand):.3f}, by category:", {c: round(v, 2) for c, v in by_category(cand).items()})
    print("  gate:", "PASS" if result["ok"] else "BLOCK")
    for reason in result["reasons"]:
        print("   -", reason)

loose = decide(base, run_eval(suite, "v3"), max_category_drop=1.0)
print("\nv3 with only the overall check:", "PASS" if loose["ok"] else "BLOCK")
