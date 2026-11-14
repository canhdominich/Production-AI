from _release import Controller, run_canary

for name, cand in [("good candidate", "good"), ("bad candidate", "bad")]:
    log, served = run_canary(cand)
    print(f"== {name} (canary 10 percent, windows of 400 requests)")
    for w, ns, nc, ms, mc, action, why in log:
        print(f"window {w}: stable {ns:3d} mean {ms:.3f} | canary {nc:3d} mean {mc:.3f} | {action:8s} {why}")
    print("requests served by the canary:", served)
    print()
