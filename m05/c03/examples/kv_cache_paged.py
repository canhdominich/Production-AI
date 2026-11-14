import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "platform"))
from workload import generate

LAYERS, KV_HEADS, HEAD_DIM, BYTES = 28, 8, 128, 2
per_token = 2 * LAYERS * KV_HEADS * HEAD_DIM * BYTES
MAX_LEN, BLOCK, BUDGET = 4096, 16, 4 * 1024**3
seqs = [min(r.prompt_tokens + r.output_tokens, MAX_LEN) for r in generate(600, seed=42)]
print(f"KV cache per token: {per_token} bytes ({per_token/1024:.0f} KiB) = 2 x {LAYERS} layers x {KV_HEADS} kv heads x {HEAD_DIM} dims x {BYTES} bytes")
print(f"{len(seqs)} sequences, mean length {sum(seqs)/len(seqs):.0f} tokens, max {max(seqs)}")
contig = per_token * MAX_LEN
paged = [(-(-n // BLOCK)) * BLOCK * per_token for n in seqs]
used = [n * per_token for n in seqs]
print(f"contiguous slot of {MAX_LEN} tokens: {contig/2**20:.0f} MiB each, {100*sum(used)/(contig*len(seqs)):.1f}% actually used")
print(f"paged blocks of {BLOCK} tokens: mean {sum(paged)/len(paged)/2**20:.1f} MiB each, {100*sum(used)/sum(paged):.1f}% actually used")
print(f"sequences that fit in {BUDGET//2**30} GiB: contiguous {BUDGET//contig}, paged {int(BUDGET//(sum(paged)/len(paged)))}")
