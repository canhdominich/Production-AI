import httpx

from _vram import CFG, MIB, activation_bytes, kv_cache_bytes, param_count, weight_bytes

BASE = "http://localhost:11434"
M = CFG["models"]["qwen3-1.7b"]


def load_and_measure(num_ctx):
    body = {"model": "qwen3:1.7b", "prompt": "hi", "stream": False, "think": False, "keep_alive": "60s",
            "options": {"num_ctx": num_ctx, "num_predict": 1}}
    httpx.post(f"{BASE}/api/generate", json=body, timeout=300).raise_for_status()
    ps = httpx.get(f"{BASE}/api/ps", timeout=30).json()["models"][0]
    return ps["size"], ps["size_vram"]


def estimate(num_ctx):
    w = weight_bytes(param_count(M, stored_output_copy=True), CFG["quant_bits_per_weight"]["q4_k_m"])
    kv = kv_cache_bytes(M, num_ctx, seqs=1)
    act = activation_bytes(M, batched_tokens=512, act_dtype_bytes=4)
    return w, kv, act


tags = httpx.get(f"{BASE}/api/tags", timeout=30).json()["models"]
file_bytes = next(t["size"] for t in tags if t["name"] == "qwen3:1.7b")
print("ollama", httpx.get(f"{BASE}/api/version", timeout=30).json()["version"], "| qwen3:1.7b Q4_K_M | CPU only, 1 sequence")
print(f"model file on disk: {file_bytes / MIB:.0f} MiB")
print("num_ctx  measured   size_vram  estimated  weights    kv  act   error  left after file+kv")
rows = []
for ctx in (2048, 4096, 8192):
    size, vram = load_and_measure(ctx)
    w, kv, act = estimate(ctx)
    est = w + kv + act
    rows.append((ctx, size))
    print(f"{ctx:>7} {size / MIB:>8.0f} MiB {vram:>6} {est / MIB:>8.0f} MiB {w / MIB:>7.0f} {kv / MIB:>5.0f} {act / MIB:>4.0f} {100 * (est - size) / size:>+6.1f}% {(size - file_bytes - kv) / MIB:>8.0f} MiB")
httpx.post(f"{BASE}/api/generate", json={"model": "qwen3:1.7b", "keep_alive": 0}, timeout=60)

slope = (rows[2][1] - rows[0][1]) / (rows[2][0] - rows[0][0])
print(f"measured growth per context token: {slope / 1024:.1f} KiB; formula says 112.0 KiB")
