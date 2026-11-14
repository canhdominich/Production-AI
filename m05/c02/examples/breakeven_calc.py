import statistics
from dataclasses import dataclass

import _paths  # noqa: F401
from common import load_json
from workload import generate

HOURS_PER_MONTH = 730


@dataclass
class SelfHost:
    gpu_per_hour: float = 1.80      # giá thuê một GPU, USD mỗi giờ (giả định)
    gpus: int = 1
    ops_per_month: float = 250.0    # công vận hành: giám sát, cập nhật, trực
    tokens_per_second: float = 1200.0  # tổng token ra mỗi giây khi máy bận (giả định)

    def fixed_cost(self):
        return self.gpu_per_hour * self.gpus * HOURS_PER_MONTH + self.ops_per_month

    def capacity_output_tokens(self):
        return self.tokens_per_second * self.gpus * HOURS_PER_MONTH * 3600


def api_cost_per_request(price, avg_in, avg_out):
    return (avg_in * price["input_per_mtok"] + avg_out * price["output_per_mtok"]) / 1_000_000


def breakeven_requests(host, per_request_api):
    return host.fixed_cost() / per_request_api


def utilization(host, requests_per_month, avg_out):
    return requests_per_month * avg_out / host.capacity_output_tokens()


requests = generate(2000, seed=42)
avg_in = statistics.mean(r.prompt_tokens for r in requests)
avg_out = statistics.mean(r.output_tokens for r in requests)
prices = load_json("prices.json")["models"]
host = SelfHost()

print(f"self-host fixed cost: {host.fixed_cost():,.0f} USD per month, capacity {host.capacity_output_tokens() / 1e9:.2f} billion output tokens per month")
print(f"average request: {avg_in:.0f} tokens in, {avg_out:.0f} tokens out\n")
print("API model     per request   break-even requests   utilization needed")
for model, price in prices.items():
    per_request = api_cost_per_request(price, avg_in, avg_out)
    be = breakeven_requests(host, per_request)
    print(f"{model:<12} {per_request:11.6f} {be:21,.0f} {utilization(host, be, avg_out):18.1%}")

print("\nFixed GPU against fake-medium API as traffic grows")
print("requests per month   API cost   self-host   utilization   cheaper")
medium = api_cost_per_request(prices["fake-medium"], avg_in, avg_out)
for n in (100_000, 500_000, 1_000_000, 2_000_000, 5_000_000, 10_000_000):
    api = n * medium
    u = utilization(host, n, avg_out)
    print(f"{n:>18,} {api:10,.0f} {host.fixed_cost():11,.0f} {u:12.1%}   {'self-host' if api > host.fixed_cost() and u <= 1 else 'API' if api <= host.fixed_cost() else 'needs more GPUs'}")
