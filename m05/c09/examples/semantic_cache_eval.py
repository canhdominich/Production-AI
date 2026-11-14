import random
import time

import numpy as np
from _toolkit import entities, load_embedder, messages_truth, strip_marks, surface_variant, truth_key

rows = list(messages_truth().values())
rnd = random.Random(7)
anchors = rnd.sample([r for r in rows if r["template_id"] != "x"], 150)
anchor_ids = {r["message_id"] for r in anchors}
anchor_truth = {truth_key(r) for r in anchors}

queries = []
for r in anchors:
    queries.append(("same question, new wording", surface_variant(r["text"], rnd), truth_key(r)))
for r in anchors:
    sibs = [x for x in rows if x["template_id"] == r["template_id"] and x["message_id"] not in anchor_ids and truth_key(x) not in anchor_truth]
    if sibs:
        queries.append(("same template, other order", rnd.choice(sibs)["text"], None))
for r in anchors[:100]:
    others = [x for x in rows if x["intent"] == r["intent"] and x["template_id"] != r["template_id"] and x["message_id"] not in anchor_ids]
    queries.append(("same intent, other question", rnd.choice(others)["text"], None))
by_text = {r["text"]: r for r in rows}
queries = [(k, t, tr if tr else truth_key(by_text[t])) for k, t, tr in queries]

embed = load_embedder()
embed(["warm up"])
A = embed([r["text"] for r in anchors])
Q = embed([q[1] for q in queries])
t0 = time.perf_counter()
for q in queries[:20]:
    embed([q[1]])
embed_ms = (time.perf_counter() - t0) / 20 * 1000

sims = Q @ A.T
best = sims.argmax(axis=1)
score = sims.max(axis=1)
a_truth = [truth_key(r) for r in anchors]
a_ents = [entities(r["text"]) for r in anchors]
kinds = sorted({q[0] for q in queries})
print(f"{len(anchors)} cached questions, {len(queries)} new queries, embedding {embed_ms:.0f} ms per query on CPU")
for kind in kinds:
    ss = [score[i] for i, q in enumerate(queries) if q[0] == kind]
    print(f"median best cosine, {kind:28}: {np.median(ss):.3f}")
print()
print(f"{'threshold':>9} {'guard':>5} {'hits':>5} {'wrong':>5} {'wrong/hits':>10} {'found same-question':>20}")
for thr in (0.80, 0.85, 0.90, 0.93, 0.96):
    for guard in (False, True):
        hits = wrong = good = 0
        for i, (kind, text, tr) in enumerate(queries):
            j = best[i]
            if score[i] < thr or (guard and entities(text) != a_ents[j]):
                continue
            hits += 1
            if a_truth[j] != tr:
                wrong += 1
            elif kind == "same question, new wording":
                good += 1
        n_pos = sum(q[0] == "same question, new wording" for q in queries)
        print(f"{thr:>9.2f} {'on' if guard else 'off':>5} {hits:>5} {wrong:>5} {wrong / max(1, hits):>10.1%} {good:>11}/{n_pos}")
