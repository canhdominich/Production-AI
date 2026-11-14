import csv

import numpy as np
import torch
from sentence_transformers import CrossEncoder, SentenceTransformer

import _paths  # noqa: F401
from common import LAB_DIR

torch.set_num_threads(2)
DATA = LAB_DIR / "m03" / "data"
with open(DATA / "docs_index.csv", encoding="utf-8") as f:
    titles = {}
    for row in csv.DictReader(f):
        titles[row["doc_id"]] = row["title"]
with open(DATA / "questions.csv", encoding="utf-8") as f:
    questions = [r for r in csv.DictReader(f) if r["gold_doc_id"] in titles and r["expected_behavior"] == "answer"]

ids = list(titles)
embedder = SentenceTransformer("intfloat/multilingual-e5-small", device="cpu")
doc_vecs = embedder.encode([f"passage: {titles[i]}" for i in ids], normalize_embeddings=True, batch_size=32)
q_vecs = embedder.encode([f"query: {q['question']}" for q in questions], normalize_embeddings=True, batch_size=32)
top = np.argsort(-(q_vecs @ doc_vecs.T), axis=1)[:, :10]


def hit_at_1(order_per_query):
    return sum(ids[o[0]] == q["gold_doc_id"] for o, q in zip(order_per_query, questions)) / len(questions)


print(f"questions with a gold document: {len(questions)}, candidate titles: {len(ids)}")
print(f"stage 1 e5-small   hit@1 = {hit_at_1(top):.3f}   hit@10 = {sum(ids.index(q['gold_doc_id']) in t for t, q in zip(top, questions)) / len(questions):.3f}")
for name in ("cross-encoder/ms-marco-TinyBERT-L2-v2", "cross-encoder/ms-marco-MiniLM-L6-v2"):
    ce = CrossEncoder(name, device="cpu")
    reordered = []
    for t, q in zip(top, questions):
        scores = ce.predict([(q["question"], titles[ids[i]]) for i in t], batch_size=10, show_progress_bar=False)
        reordered.append([t[j] for j in np.argsort(-np.asarray(scores))])
    print(f"stage 2 {name.split('/')[1]:<28} hit@1 = {hit_at_1(reordered):.3f}")
