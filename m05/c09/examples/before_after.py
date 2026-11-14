import asyncio

import redis.asyncio as aredis
from _toolkit import (DURATION_S, EMBED_COST_S, N_REQUESTS, PROVIDER_CFG, SLOTS, PORT_REDIS, SCALE, AsyncGateway, ExactCache, Limiter, SemanticCache, embed_lookup, fake_provider, load_embedder,
                      make_traffic, provider_stats, redis_server, run_open_loop, summarize)

WAIT_S = 3.0


def stages(embed):
    def limiter():
        return dict(limiter=Limiter(SLOTS))

    def bounded():
        return dict(feature_limiters={"chat": Limiter(5, max_queue=8, max_wait_s=WAIT_S * SCALE),
                                      "knowledge_assistant": Limiter(3, max_queue=6, max_wait_s=WAIT_S * SCALE),
                                      "weekly_report_agent": Limiter(2, max_queue=4, max_wait_s=30 * SCALE)})

    def exact(base):
        return dict(base, exact=ExactCache(aredis.Redis(port=PORT_REDIS, protocol=2)))

    def sem(base, thr, guard):
        return dict(base, semantic=SemanticCache(thr, guard), embed=embed, embed_cost_s=EMBED_COST_S)

    return [
        ("0 baseline, no control", lambda: {}),
        ("1 + concurrency limit 10", lambda: limiter()),
        ("2 + exact cache", lambda: exact(limiter())),
        ("3a + semantic 0.90, no guard", lambda: sem(exact(limiter()), 0.90, False)),
        ("3b + semantic 0.96, guard", lambda: sem(exact(limiter()), 0.96, True)),
        ("4 + backpressure (bounded)", lambda: sem(exact(bounded()), 0.96, True)),
    ]


async def trial(name, make, jobs):
    with fake_provider(**PROVIDER_CFG) as base:
        kw = make()
        if "exact" in kw:
            await kw["exact"].r.flushdb()
        gw = AsyncGateway(base, **kw)
        results, wall = await run_open_loop(gw, jobs)
        await gw.aclose()
        if "exact" in kw:
            await kw["exact"].r.aclose()
        calls = provider_stats(base)["requests"]
    s = summarize(results, wall)
    s["calls"] = calls
    return name, s


async def main():
    jobs = make_traffic(N_REQUESTS, duration_s=DURATION_S)
    embed = embed_lookup(jobs, load_embedder())
    rows = []
    with redis_server():
        for name, make in stages(embed):
            rows.append(await trial(name, make, jobs))
    print(f"{'stage':30}{'served':>7}{'reject':>7}{'error':>6}{'TTFT p50':>9}{'TTFT p95':>9}{'SLO ok':>8}{'goodput':>9}")
    for name, s in rows:
        print(f"{name:30}{s['served']:>7}{s['rejected']:>7}{s['errors']:>6}{s['ttft_p50']:>9.2f}{s['ttft_p95']:>9.2f}{s['slo_ok']:>8.0%}{s['goodput']:>9.1f}")
    print()
    print(f"{'stage':30}{'provider calls':>15}{'cache hits':>11}{'wrong hits':>11}{'spend USD':>10}")
    for name, s in rows:
        print(f"{name:30}{s['calls']:>15}{s['hits']:>11}{s['wrong_hits']:>11}{s['cost']:>10.3f}")


asyncio.run(main())
