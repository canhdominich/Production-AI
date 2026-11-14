from _sec import check_key, hash_key, new_api_key

store = {}
issued = {}
for tenant in ("br-cau-go", "br-ben-song"):
    kid, full = new_api_key()
    store[kid] = {"tenant": tenant, "hash": hash_key(full), "revoked": False}
    issued[tenant] = full

cg = issued["br-cau-go"]
print("key shape      :", cg[:3] + "<id 8 hex>_<43 url-safe chars>", f"({len(cg)} chars)")
print("stored in table:", [(v["tenant"], len(v["hash"]), "hex chars of sha256") for v in store.values()])
print("valid key      ->", check_key(store, cg))
print("one char off   ->", check_key(store, cg[:-1] + ("A" if cg[-1] != "A" else "B")))
print("unknown id     ->", check_key(store, "gd_deadbeef_" + cg.split("_", 2)[2]))

kid = cg.split("_")[1]
store[kid]["revoked"] = True
print("after revoke   ->", check_key(store, cg))

print("--- what a leaked table gives an attacker")
RATE = 10_000_000_000
print(f"assumed attacker speed: {RATE:,} sha256 per second (GPU class, assumption)")
years = 2 ** 256 / RATE / (3600 * 24 * 365)
print(f"random 32-byte secret: 2^256 possibilities, about {years:.0e} years")
print(f"6-character lowercase+digit secret: {36 ** 6:,} possibilities, {36 ** 6 / RATE:.2f} seconds")
