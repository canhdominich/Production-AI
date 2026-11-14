import os
import sys
from pathlib import Path

_default = Path(__file__).resolve().parents[3] / "platform"
PLATFORM_DIR = Path(os.environ.get("ANHTI_PLATFORM_DIR", _default))
DATA_DIR = Path(os.environ.get("ANHTI_DATA_DIR", PLATFORM_DIR.parent / "data"))
if str(PLATFORM_DIR) not in sys.path:
    sys.path.insert(0, str(PLATFORM_DIR))

from gateway_core import (  # noqa: E402
    FeatureNotAllowed,
    Gateway,
    GatewayError,
    GatewayRequest,
    PriceTable,
    ProviderClient,
    ProviderError,
    ProviderResult,
    TenantRegistry,
    UnknownTenant,
    UsageRecord,
    UsageSink,
)
from common import estimate_prompt_tokens, percentile  # noqa: E402

__all__ = [
    "DATA_DIR", "FeatureNotAllowed", "Gateway", "GatewayError", "GatewayRequest", "PriceTable", "ProviderClient",
    "ProviderError", "ProviderResult", "TenantRegistry", "UnknownTenant", "UsageRecord", "UsageSink",
    "estimate_prompt_tokens", "percentile",
]
