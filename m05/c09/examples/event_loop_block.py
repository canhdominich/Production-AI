import asyncio
import time

CALLS = 20
CALL_S = 0.2


async def blocking_handler():
    time.sleep(CALL_S)


async def awaiting_handler():
    await asyncio.sleep(CALL_S)


async def threaded_handler():
    await asyncio.to_thread(time.sleep, CALL_S)


async def heartbeat(gaps, stop):
    last = time.perf_counter()
    while not stop.is_set():
        await asyncio.sleep(0.01)
        now = time.perf_counter()
        gaps.append(now - last)
        last = now


async def trial(handler):
    gaps, stop = [], asyncio.Event()
    beat = asyncio.create_task(heartbeat(gaps, stop))
    await asyncio.sleep(0.05)
    t0 = time.perf_counter()
    await asyncio.gather(*(handler() for _ in range(CALLS)))
    wall = time.perf_counter() - t0
    stop.set()
    await beat
    return wall, max(gaps)


async def main():
    print(f"{CALLS} requests, each waits {CALL_S * 1000:.0f} ms on a provider")
    print(f"{'handler':34}{'all done after':>16}{'longest freeze of other work':>32}")
    for name, h in (("sync call inside async def", blocking_handler), ("await the call", awaiting_handler), ("sync call in a worker thread", threaded_handler)):
        wall, freeze = await trial(h)
        print(f"{name:34}{wall * 1000:>13.0f} ms{freeze * 1000:>29.0f} ms")


asyncio.run(main())
