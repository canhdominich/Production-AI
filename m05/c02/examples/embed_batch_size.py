import time

import torch
from sentence_transformers import SentenceTransformer

torch.set_num_threads(2)
model = SentenceTransformer("intfloat/multilingual-e5-small", device="cpu")
texts = [f"query: Đơn AT{100000 + i} của chi nhánh {['Cầu Gỗ', 'Bến Sông', 'Xóm Vui', 'Đầu Phố'][i % 4]} giao trễ bao lâu rồi?" for i in range(96)]
model.encode(texts[:8], batch_size=8)

print(f"model dimension {model.get_sentence_embedding_dimension()}, parameters {sum(p.numel() for p in model.parameters()) / 1e6:.0f}M, texts {len(texts)}")
print("batch_size   seconds   texts per second   speedup")
base = None
for batch_size in (1, 4, 16, 48, 96):
    best = min(
        (lambda t0: (model.encode(texts, batch_size=batch_size, show_progress_bar=False), time.perf_counter() - t0)[1])(time.perf_counter())
        for _ in range(3)
    )
    base = base or best
    print(f"{batch_size:>10} {best:9.2f} {len(texts) / best:18.1f} {base / best:9.2f}x")
