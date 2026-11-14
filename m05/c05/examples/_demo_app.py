import asyncio
import json

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/echo")
async def echo(request: Request):
    body = await request.body()
    return {"bytes": len(body)}


@app.get("/stream")
async def stream():
    async def gen():
        for i in range(6):
            yield json.dumps({"token": i}) + "\n"
            await asyncio.sleep(0.25)

    return StreamingResponse(gen(), media_type="application/x-ndjson")


produced = {"n": 0}


@app.get("/long")
async def long():
    produced["n"] = 0

    async def gen():
        for i in range(40):
            produced["n"] += 1
            yield json.dumps({"token": i}) + "\n"
            await asyncio.sleep(0.1)

    return StreamingResponse(gen(), media_type="application/x-ndjson")


@app.get("/stats")
async def stats():
    return produced
