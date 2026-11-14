from _sec import AuthError, issue_token, verify_token

DAY = 86400
T0 = 1_800_000_000
TTL = 900
keyring = {"2026-q4": "signing-secret-2026-q4-0123456789abcdef"}
active = "2026-q4"
issued = []


def issue_batch(now, n, label):
    for i in range(n):
        issued.append((label, issue_token(keyring, active, "br-cau-go", f"cg-{i:02d}", "branch_lead", now, ttl=TTL)))


def accepted(now):
    ok = 0
    for _, tok in issued:
        try:
            verify_token(keyring, tok, now)
            ok += 1
        except AuthError:
            pass
    return ok


issue_batch(T0, 100, "before")
print("day 0   key 2026-q4 only           :", accepted(T0 + 60), "of", len(issued), "tokens accepted")

keyring["2027-q1"] = "signing-secret-2027-q1-fedcba9876543210"
active = "2027-q1"
issue_batch(T0 + 120, 100, "after")
print("day 0   rotate: add 2027-q1, sign new:", accepted(T0 + 180), "of", len(issued), "(both keys verify)")

old_key = keyring.pop("2026-q4")
print("+10 min retire 2026-q4 too early    :", accepted(T0 + 600), "of", len(issued), "(old tokens cut off while still valid)")
keyring["2026-q4"] = old_key
print("+16 min old tokens expired          :", accepted(T0 + 930), "of", len(issued), "(only the new batch is left)")
del keyring["2026-q4"]
print("+16 min retire 2026-q4 afterwards   :", accepted(T0 + 930), "of", len(issued), "(no valid token lost)")

print("--- leaked secret")
leaked = {"2027-q1": keyring["2027-q1"]}
forged = issue_token(leaked, "2027-q1", "br-dau-pho", "attacker", "branch_manager", T0 + 2000)
try:
    c = verify_token(keyring, forged, T0 + 2010)
    print("forged token with leaked key       : accepted as", c["tenant"], c["role"])
except AuthError as e:
    print("forged token                       : rejected", e)
keyring["2027-q2"] = "signing-secret-2027-q2-1122334455667788"
active = "2027-q2"
del keyring["2027-q1"]
try:
    verify_token(keyring, forged, T0 + 2020)
except AuthError as e:
    print("after emergency rotation            : forged token rejected", e)
fresh = issue_token(keyring, active, "br-cau-go", "cg-01", "branch_lead", T0 + 2030)
print("legitimate user logs in again       :", verify_token(keyring, fresh, T0 + 2040)["tenant"])
