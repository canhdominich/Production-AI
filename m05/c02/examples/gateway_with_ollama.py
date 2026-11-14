import time
from pathlib import Path

import httpx

import _paths  # noqa: F401
from gateway_core import Gateway, GatewayRequest, PriceTable, ProviderClient, ProviderError, ProviderResult


class OllamaClient(ProviderClient):
    def complete(self, model, messages, max_tokens=None, request_id=None, output_tokens=None, timeout_s=None):
        body = {"model": model, "messages": messages, "max_tokens": max_tokens or 100, "reasoning_effort": "none", "temperature": 0, "seed": 7}
        t0 = time.perf_counter()
        try:
            r = self._http.post(f"{self.base_url}/v1/chat/completions", json=body, timeout=timeout_s or self.timeout_s)
        except httpx.TransportError as e:
            raise ProviderError("connection", None, None, str(e)) from None
        self._raise_for(r)
        d, total = r.json(), time.perf_counter() - t0
        return ProviderResult(d["choices"][0]["message"]["content"], d["usage"]["prompt_tokens"], d["usage"]["completion_tokens"], total, total, d["choices"][0]["finish_reason"])


gateway = Gateway([OllamaClient("ollama", "http://localhost:11434", timeout_s=120)], prices=PriceTable(Path(__file__).with_name("prices_selfhost.json")))
questions = ["Giao hàng nội thành mất bao lâu? Trả lời một câu.", "Khách đổi địa chỉ sau khi lấy hàng thì làm gì? Trả lời một câu."]
print("tenant      feature  model        provider  in  out  cost_usd   latency_s  text")
for i, q in enumerate(questions):
    res = gateway.handle(GatewayRequest("br-cau-go", "chat", [{"role": "user", "content": q}], tier="small", request_id=f"c02-{i}", max_tokens=60))
    r = res.record
    print(f"{r.tenant_id:<11} {r.feature:<8} {r.model:<12} {r.provider:<8} {r.prompt_tokens:>3} {r.output_tokens:>4} {r.cost_usd:10.6f} {r.latency_ms / 1000:10.1f}  {res.text[:40]!r}")
print(f"total cost of {len(gateway.sink.records)} calls: {gateway.sink.total_cost():.6f} USD")
