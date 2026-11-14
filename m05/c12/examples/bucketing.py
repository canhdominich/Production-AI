import random
from collections import Counter

from _release import route

users = [f"user-{i}" for i in range(2000)]
sticky = Counter(route(u, 10) for u in users)
print("sticky routing, 2000 users:", dict(sticky))

rnd = random.Random(3)
flips = 0
for u in users[:500]:
    seen = {("canary" if rnd.random() < 0.10 else "stable") for _ in range(5)}
    flips += len(seen) == 2
print("per-request coin flip, users who saw both versions in 5 chats:", flips, "of 500")
print("sticky routing, same check:", sum(len({route(u, 10) for _ in range(5)}) == 2 for u in users[:500]), "of 500")

grow = sum(route(u, 10) == "canary" for u in users)
grow25 = sum(route(u, 25) == "canary" for u in users)
kept = sum(route(u, 10) == "canary" and route(u, 25) == "canary" for u in users)
print(f"10 percent canary users: {grow}; at 25 percent: {grow25}; of the first group still in canary: {kept}")
