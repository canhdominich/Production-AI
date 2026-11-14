import shutil
import sys

from _dock import STACK, TMP

sys.path.insert(0, str(STACK.parent / "lab" / "solution"))
import stack_review as sr

naive = TMP / "review_naive"
shutil.rmtree(naive, ignore_errors=True)
naive.mkdir(parents=True)
shutil.copy(STACK / "variants" / "Dockerfile.naive", naive / "Dockerfile")
shutil.copy(STACK / "variants" / "compose.naive.yaml", naive / "compose.yaml")

print("reference stack (c04/stack):")
print("\n".join("  " + x for x in sr.review(STACK)))
print("naive stack (Dockerfile.naive, compose.naive.yaml):")
print("\n".join("  " + x for x in sr.review(naive)))
shutil.rmtree(naive, ignore_errors=True)
print("weights_strategy:", [(mb, h, sr.weights_strategy(mb, h)) for mb, h in ((90, 3), (1400, 1), (1400, 3))])
