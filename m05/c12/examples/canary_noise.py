from _release import Controller, run_canary

naive = Controller(margin=0.0, z=0.0, min_samples=1, strikes=1)
log, served = run_canary("good", controller=naive)
print("naive rule (any drop, one strike), good candidate:")
for w, ns, nc, ms, mc, action, why in log:
    print(f"window {w}: canary mean {mc:.3f} vs stable {ms:.3f} -> {action}")
print()
log, served = run_canary("good", controller=Controller())
print("careful rule, same traffic:", [a for *_, a, _ in log])
