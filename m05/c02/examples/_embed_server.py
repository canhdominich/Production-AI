import argparse
import asyncio
import time

import torch
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

torch.set_num_threads(2)


class EmbeddingRequest(BaseModel):
    model: str = "intfloat/multilingual-e5-small"
    input: str | list[str]


class MicroBatcher:
    def __init__(self, encode, max_batch, wait_ms):
        self.encode, self.max_batch, self.wait = encode, max_batch, wait_ms / 1000
        self.queue = asyncio.Queue()
        self.batches = []

    async def submit(self, text):
        future = asyncio.get_running_loop().create_future()
        await self.queue.put((text, future))
        return await future

    async def run(self):
        loop = asyncio.get_running_loop()
        while True:
            batch = [await self.queue.get()]
            deadline = loop.time() + self.wait
            while len(batch) < self.max_batch and (left := deadline - loop.time()) > 0:
                try:
                    batch.append(await asyncio.wait_for(self.queue.get(), left))
                except asyncio.TimeoutError:
                    break
            vectors = await loop.run_in_executor(None, self.encode, [t for t, _ in batch])
            self.batches.append(len(batch))
            for (_, future), vec in zip(batch, vectors):
                future.set_result(vec)


def create_app(max_batch, wait_ms):
    model = SentenceTransformer("intfloat/multilingual-e5-small", device="cpu")
    batcher = MicroBatcher(lambda texts: model.encode(texts, normalize_embeddings=True, batch_size=max_batch).tolist(), max_batch, wait_ms)
    app = FastAPI()

    @app.on_event("startup")
    async def start():
        asyncio.create_task(batcher.run())

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/stats")
    def stats():
        b = batcher.batches
        return {"model_calls": len(b), "mean_batch": sum(b) / max(1, len(b)), "max_batch": max(b, default=0)}

    @app.post("/v1/embeddings")
    async def embeddings(req: EmbeddingRequest):
        texts = [req.input] if isinstance(req.input, str) else req.input
        vectors = await asyncio.gather(*[batcher.submit(t) for t in texts])
        tokens = sum(len(t.split()) for t in texts)
        return {"object": "list", "model": req.model, "usage": {"prompt_tokens": tokens, "total_tokens": tokens},
                "data": [{"object": "embedding", "index": i, "embedding": v} for i, v in enumerate(vectors)]}

    return app


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5621)
    ap.add_argument("--max-batch", type=int, default=32)
    ap.add_argument("--wait-ms", type=float, default=5)
    a = ap.parse_args()
    uvicorn.run(create_app(a.max_batch, a.wait_ms), host="127.0.0.1", port=a.port, log_level="warning")
