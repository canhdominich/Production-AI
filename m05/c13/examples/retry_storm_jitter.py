import heapq
import random
from collections import Counter

from _kit import backoff_delay

CLIENTS, CAPACITY_PER_S, MAX_RETRIES = 300, 40, 4


def simulate(jitter, seed=7):
    rnd = random.Random(seed)
    events = [(backoff_delay(0, base=2.0, cap=30.0, jitter=jitter, rnd=rnd), i, 1) for i in range(CLIENTS)]
    heapq.heapify(events)
    accepted_in_window, arrivals, done_at, gave_up = Counter(), Counter(), {}, 0
    while events:
        t, cid, k = heapq.heappop(events)
        window = int(t)
        arrivals[window] += 1
        if accepted_in_window[window] < CAPACITY_PER_S:
            accepted_in_window[window] += 1
            done_at[cid] = t
        elif k < MAX_RETRIES:
            heapq.heappush(events, (t + backoff_delay(k, base=2.0, cap=30.0, jitter=jitter, rnd=rnd), cid, k + 1))
        else:
            gave_up += 1
    return arrivals, done_at, gave_up


print(f"{CLIENTS} clients retry together after a provider blip; the provider accepts {CAPACITY_PER_S} requests per second, each client allows {MAX_RETRIES} retries after the first failure")
print(f"{'policy':<28} {'peak req/s':>10} {'total sent':>10} {'succeeded':>9} {'gave up':>8} {'last success (s)':>17}")
for label, jitter in (("exponential, no jitter", "none"), ("exponential, full jitter", "full")):
    arrivals, done_at, gave_up = simulate(jitter)
    print(f"{label:<28} {max(arrivals.values()):>10} {sum(arrivals.values()):>10} {len(done_at):>9} {gave_up:>8} {max(done_at.values()):>17.1f}")
