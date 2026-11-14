import asyncio

import pytest

from perf_toolkit import Limiter, Overloaded, SemanticCache, TTLCache, cache_key, normalize, percentile, summarize, wrong_hit_rate

MSGS = [{"role": "user", "content": "  Đơn AT000123   đến   chưa? "}]


def test_percentile_and_summary():
    assert percentile([1, 2, 3, 4], 50) == pytest.approx(2.5)
    assert percentile([5], 95) == 5.0
    with pytest.raises(ValueError):
        percentile([], 50)
    outs = [{"status": "ok", "ttft_s": 1.0}, {"status": "hit", "ttft_s": 0.0}, {"status": "rejected", "ttft_s": 0.0},
            {"status": "error", "ttft_s": 0.0}, {"status": "ok", "ttft_s": 3.0}]
    s = summarize(outs)
    assert s["n"] == 5 and s["served"] == 3
    assert s["reject_rate"] == pytest.approx(0.2) and s["error_rate"] == pytest.approx(0.2)
    assert s["ttft_p50"] == pytest.approx(1.0)


def test_cache_key_normalizes_and_isolates_tenants():
    assert normalize(MSGS[0]["content"]) == "Đơn AT000123 đến chưa?"
    same = [{"role": "user", "content": "Đơn AT000123 đến chưa?"}]
    assert cache_key("cau-go", "fake-small", MSGS) == cache_key("cau-go", "fake-small", same)
    assert cache_key("cau-go", "fake-small", MSGS) != cache_key("ben-song", "fake-small", MSGS)
    assert cache_key("cau-go", "fake-small", MSGS) != cache_key("cau-go", "fake-large", MSGS)
    lower = [{"role": "user", "content": "đơn at000123 đến chưa?"}]
    assert cache_key("cau-go", "fake-small", MSGS) != cache_key("cau-go", "fake-small", lower)


def test_ttl_cache_expires():
    now = [0.0]
    c = TTLCache(10, lambda: now[0])
    assert c.get("k") is None
    c.put("k", "v")
    now[0] = 9.9
    assert c.get("k") == "v"
    now[0] = 10.0
    assert c.get("k") is None
    assert (c.hits, c.misses) == (1, 2)


def test_semantic_cache_guard_blocks_other_order_code():
    scope = ("cau-go", "fake-small")
    sc = SemanticCache(0.9, guard=True)
    sc.add(scope, [1.0, 0.0], "don AT000123 den chua", "A")
    assert sc.lookup(scope, [0.99, 0.05], "don AT000123 toi chua") == "A"
    assert sc.lookup(scope, [0.99, 0.05], "don AT000999 den chua") is None
    assert sc.lookup(("ben-song", "fake-small"), [1.0, 0.0], "don AT000123 den chua") is None
    assert sc.lookup(scope, [0.0, 1.0], "don AT000123 den chua") is None
    loose = SemanticCache(0.9, guard=False)
    loose.add(scope, [1.0, 0.0], "don AT000123 den chua", "A")
    assert loose.lookup(scope, [0.99, 0.05], "don AT000999 den chua") == "A"


def test_wrong_hit_rate():
    res = [{"hit": True, "correct": True}, {"hit": True, "correct": False}, {"hit": False, "correct": False},
           {"hit": True, "correct": True}, {"hit": True, "correct": True}]
    assert wrong_hit_rate(res) == pytest.approx(0.25)
    assert wrong_hit_rate([{"hit": False, "correct": False}]) == 0.0


def test_limiter_rejects_when_queue_is_full():
    async def scenario():
        lim = Limiter(max_concurrent=1, max_queue=1)
        order = []

        async def job(name, hold):
            async with lim:
                order.append(name)
                await asyncio.sleep(hold)

        t1 = asyncio.create_task(job("a", 0.05))
        await asyncio.sleep(0.01)
        t2 = asyncio.create_task(job("b", 0.01))
        await asyncio.sleep(0.01)
        with pytest.raises(Overloaded):
            await job("c", 0.01)
        await asyncio.gather(t1, t2)
        assert order == ["a", "b"]
        async with lim:
            pass

    asyncio.run(scenario())
