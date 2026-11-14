import httpx

BASE = "http://localhost:11434"
BODY = {"model": "qwen3:1.7b", "prompt": "hi", "stream": False, "think": False, "options": {"num_predict": 1, "num_ctx": 2048}}


def call(keep_alive):
    r = httpx.post(f"{BASE}/api/generate", json=dict(BODY, keep_alive=keep_alive), timeout=300).json()
    return r["load_duration"] / 1e9, r["total_duration"] / 1e9


print("run  state            load_s  total_s")
for i in range(1, 4):
    httpx.post(f"{BASE}/api/generate", json={"model": "qwen3:1.7b", "keep_alive": 0}, timeout=60)
    load, total = call("30s")
    print(f"{i:>3}  cold (unloaded)  {load:>6.2f}  {total:>7.2f}")
    load, total = call("0")
    print(f"{i:>3}  warm (loaded)    {load:>6.2f}  {total:>7.2f}")
