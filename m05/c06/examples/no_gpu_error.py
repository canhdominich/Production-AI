import torch

print("torch", torch.__version__, "| cuda available:", torch.cuda.is_available(), "| devices:", torch.cuda.device_count())
weights = torch.zeros(1024, 1024, dtype=torch.bfloat16)
print("CPU tensor ok:", weights.shape, weights.dtype, weights.numel() * weights.element_size() // 1024, "KiB")
weights.to("cuda")
