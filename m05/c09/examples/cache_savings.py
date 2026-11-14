from _toolkit import EMBED_COST_S, SemanticCache, cache_key, embed_lookup, load_embedder, make_traffic
from gateway_core import PriceTable

prices = PriceTable()
jobs = make_traffic(1500, seed=42, duration_s=900)
embed = embed_lookup(jobs, load_embedder())
total = sum(prices.cost(j.req.model, j.req.prompt_tokens, j.req.output_tokens) for j in jobs)
chat_cacheable = sum(j.cacheable for j in jobs)


def replay(threshold, guard):
    exact, sem = {}, SemanticCache(threshold, guard) if threshold else None
    saved = hits_exact = hits_sem = wrong = lookups = 0
    for j in jobs:
        r = j.req
        if not j.cacheable:
            continue
        key = cache_key(r.tenant_id, r.model, r.messages, r.max_tokens)
        cost = prices.cost(r.model, r.prompt_tokens, r.output_tokens)
        if key in exact:
            hits_exact += 1
            saved += cost
            continue
        if sem is not None:
            lookups += 1
            vec = embed(j.text)
            entry, _ = sem.lookup((r.tenant_id, r.model), vec, j.text)
            if entry is not None:
                hits_sem += 1
                saved += cost
                wrong += entry["truth"] != j.truth
                exact[key] = True
                continue
            sem.add((r.tenant_id, r.model), vec, j.text, {}, j.truth)
        exact[key] = True
    return hits_exact, hits_sem, wrong, lookups, saved


print(f"{len(jobs)} requests, {chat_cacheable} first-turn chat questions are cacheable, spend without cache ${total:.4f}")
print(f"{'policy':34}{'exact':>6}{'semantic':>9}{'wrong':>6}{'wrong/sem':>10}{'saved':>9}{'embed CPU s':>12}")
for name, thr, guard in (("exact only", 0, True), ("semantic 0.90, no guard", 0.90, False), ("semantic 0.96, number guard", 0.96, True)):
    he, hs, w, lk, saved = replay(thr, guard)
    print(f"{name:34}{he:>6}{hs:>9}{w:>6}{w / max(1, hs):>10.1%}{saved / total:>9.1%}{lk * EMBED_COST_S:>12.1f}")
