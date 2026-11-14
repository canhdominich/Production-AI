from collections import Counter

from _genai import ObservedGateway
from _support import provider
from gateway_core import GatewayRequest, ProviderClient
from workload import generate

reqs = generate(60, seed=42)


def run(gw, max_tokens):
    rows = []
    for r in reqs:
        gr = GatewayRequest(r.tenant_id, r.feature, r.messages, r.tier, r.role, r.request_id, max_tokens=max_tokens, output_tokens=r.output_tokens)
        resp = gw.handle(gr)
        rows.append((r.feature, 200, gr.finish_reason, resp.record.output_tokens))
    return rows


def show(title, rows):
    print(title)
    print(f"{'feature':22}{'requests':>9}{'HTTP 200':>10}{'finish=length':>15}")
    for f in ("chat", "knowledge_assistant", "weekly_report_agent"):
        part = [x for x in rows if x[0] == f]
        cut = sum(1 for x in part if x[2] == "length")
        print(f"{f:22}{len(part):>9}{len(part):>10}{cut:>15}")
    total_cut = sum(1 for x in rows if x[2] == "length")
    print(f"{'all':22}{len(rows):>9}{len(rows):>10}{total_cut:>15}   error rate 0.0%, truncated {100 * total_cut / len(rows):.1f}%")


with provider(5671, time_scale=0.01) as url:
    gw = ObservedGateway([ProviderClient("fake", url)])
    show("Before: max_tokens = 4096", run(gw, 4096))
    print()
    show("After a cost-saving change: max_tokens = 150", run(gw, 150))
