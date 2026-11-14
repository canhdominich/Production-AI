import csv
import sys
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

rows = list(csv.DictReader(open(Path(__file__).resolve().parents[3] / "m02" / "data" / "messages.csv", encoding="utf-8")))
tr = [r for r in rows if r["split"] == "train"]
te = [r for r in rows if r["split"] == "test"]
vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=2)
X = vec.fit_transform([r["text"].lower() for r in tr])
clf = LogisticRegression(max_iter=2000).fit(X, [r["intent"] for r in tr])
Xt = vec.transform([r["text"].lower() for r in te])
yt = np.array([r["intent"] for r in te])
W = clf.coef_.copy()
print(f"train {len(tr)}, test {len(te)}, weights {W.shape[0]} x {W.shape[1]} = {W.size} numbers")


def quantize(w, bits, group):
    levels = 2 ** (bits - 1) - 1
    flat = w.reshape(-1, group)
    scale = np.abs(flat).max(axis=1, keepdims=True) / levels
    scale[scale == 0] = 1
    return (np.round(flat / scale).clip(-levels, levels) * scale).reshape(w.shape)


def acc(w):
    return float((np.array(clf.classes_)[(Xt @ w.T + clf.intercept_).argmax(axis=1)] == yt).mean())


pad = (-W.shape[1]) % 64
Wp = np.pad(W, ((0, 0), (0, pad)))
print("bits  group   mean abs error   test accuracy   weight size")
print(f"fp32     -    {0:14.6f}   {acc(W):13.3f}   {W.size*4/1024:7.1f} KiB")
for bits in (8, 4, 3, 2):
    for group in (Wp.shape[1], 64):
        q = quantize(Wp, bits, group)[:, :W.shape[1]]
        size = W.size * bits / 8 / 1024 + (0 if group == Wp.shape[1] else W.size / group * 2 / 1024)
        print(f"{bits:>4} {('row' if group == Wp.shape[1] else group):>6}   {np.abs(q - W).mean():14.6f}   {acc(q):13.3f}   {size:7.1f} KiB")
