from _harness import PLATFORM
from gateway_core import Gateway, GatewayRequest, ProviderClient

gateway = Gateway([ProviderClient("provider-a", "http://127.0.0.1:5610")])
gateway.handle(GatewayRequest("br-ha-noi", "chat", [{"role": "user", "content": "Don AT123456 o dau?"}]))
