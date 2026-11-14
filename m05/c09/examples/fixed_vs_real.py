import asyncio
import dataclasses

from _toolkit import DURATION_S, N_REQUESTS, PROVIDER_CFG, SLOTS, AsyncGateway, Job, fake_provider, make_traffic, print_table, provider_stats, run_open_loop, summarize

FIXED_PROMPT = [{"role": "system", "content": "Bạn là trợ lý chăm sóc khách hàng."}, {"role": "user", "content": "Đơn AT000123 của tôi đến chưa?"}]


def as_fixed(jobs):
    out = []
    for j in jobs:
        r = dataclasses.replace(j.req, feature="chat", model="fake-medium", stream=True, messages=FIXED_PROMPT, output_tokens=128, max_tokens=2048)
        out.append(Job(r))
    return out


async def trial(name, jobs):
    with fake_provider(**PROVIDER_CFG) as base:
        gw = AsyncGateway(base)
        results, wall = await run_open_loop(gw, jobs)
        await gw.aclose()
        peak = provider_stats(base)["max_inflight"]
    s = summarize(results, wall)
    s["peak"] = peak
    s["tokens"] = sum(o.out_tokens for o in results)
    return name, s


async def main():
    real = make_traffic(N_REQUESTS, duration_s=DURATION_S)
    rows = [await trial("fixed: 128 tokens each", as_fixed(real)), await trial("realistic length mix", real)]
    print_table(rows, extra=("peak", "tokens"))


asyncio.run(main())
