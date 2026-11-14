import sys

sys.path.insert(0, "/srv/platform")

from gateway_core import Gateway, GatewayError, GatewayRequest, ProviderClient

from app import settings


def make_gateway():
    return Gateway([ProviderClient("provider-a", settings.PROVIDER_URL, timeout_s=30)])


__all__ = ["make_gateway", "GatewayRequest", "GatewayError"]
