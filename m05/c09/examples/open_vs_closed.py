import asyncio

from _toolkit import DURATION_S, N_REQUESTS, PROVIDER_CFG, SLOTS, AsyncGateway, Limiter, fake_provider, make_traffic, print_table, run_closed_loop, run_open_loop, summarize



async def trial(mode):
    jobs = make_traffic(N_REQUESTS, duration_s=DURATION_S)
    with fake_provider(**PROVIDER_CFG) as base:
        gw = AsyncGateway(base, limiter=Limiter(SLOTS))
        if mode == "open":
            results, wall = await run_open_loop(gw, jobs)
        else:
            results, wall = await run_closed_loop(gw, jobs, workers=SLOTS)
        await gw.aclose()
    s = summarize(results, wall)
    s["waiting"] = gw.limiter.peak_waiting
    return s


async def main():
    rows = [("closed loop, 10 workers", await trial("closed")), ("open loop, arrival curve", await trial("open"))]
    print_table(rows, extra=("waiting",))


asyncio.run(main())
