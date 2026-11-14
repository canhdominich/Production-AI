import pytest
from fastapi.testclient import TestClient

from fake_provider import Config, create_app
from gateway_core import (FeatureNotAllowed, Gateway, GatewayRequest, PriceTable, ProviderClient, ProviderError, TenantRegistry,
                          UnknownTenant, UsageRecord)

MSG = [{"role": "user", "content": "Đơn AT123456 ở đâu?"}]


class AppClient(ProviderClient):
    def __init__(self, name, test_client):
        self.name = name
        self.base_url = ""
        self.api_key = "x"
        self.timeout_s = 5
        self._http = test_client


def provider(**cfg):
    return AppClient("fake-a", TestClient(create_app(Config(time_scale=0.0, **cfg))))


def test_tenants_loaded():
    reg = TenantRegistry()
    assert len(reg.all()) == 5
    assert reg.get("br-ben-song").max_tier == "medium"
    assert reg.by_api_key("demo-key-cau-go").tenant_id == "br-cau-go"
    with pytest.raises(UnknownTenant):
        reg.get("br-nowhere")
    with pytest.raises(UnknownTenant):
        reg.by_api_key("bad")


def test_feature_check_by_tenant_and_role():
    reg = TenantRegistry()
    bs = reg.get("br-ben-song")
    with pytest.raises(FeatureNotAllowed):
        reg.check_feature(bs, "weekly_report_agent")
    reg.check_feature(reg.get("br-dau-pho"), "weekly_report_agent", "branch_manager")
    with pytest.raises(FeatureNotAllowed):
        reg.check_feature(reg.get("br-dau-pho"), "weekly_report_agent", "cskh_agent")


def test_price_table_cost_and_flag():
    p = PriceTable()
    assert p.illustrative is True
    assert p.cost("fake-medium", 1_000_000, 0) == pytest.approx(0.75)
    assert p.cost("fake-medium", 0, 1_000_000) == pytest.approx(3.0)
    assert p.cost("fake-medium", 1_000_000, 0, cached_tokens=1_000_000) == pytest.approx(0.20)
    assert p.model_for("large") == "fake-large" and p.tier_of("fake-small") == "small"


def test_gateway_writes_usage_record_with_cost():
    gw = Gateway([provider()])
    resp = gw.handle(GatewayRequest("br-cau-go", "chat", MSG, tier="small", role="cskh_agent", output_tokens=30, request_id="g1"))
    rec = resp.record
    assert isinstance(rec, UsageRecord) and rec.status == "ok" and rec.output_tokens == 30 and rec.model == "fake-small"
    assert rec.cost_usd == pytest.approx(gw.prices.cost("fake-small", rec.prompt_tokens, 30))
    assert gw.sink.records == [rec]
    assert gw.sink.total_cost(tenant_id="br-cau-go") == pytest.approx(rec.cost_usd)


def test_gateway_caps_tier_by_tenant_plan():
    gw = Gateway([provider()])
    resp = gw.handle(GatewayRequest("br-ben-song", "chat", MSG, tier="large", output_tokens=5))
    assert resp.record.model == "fake-medium"


def test_gateway_rejects_unknown_tenant_and_feature():
    gw = Gateway([provider()])
    with pytest.raises(UnknownTenant):
        gw.handle(GatewayRequest("br-nowhere", "chat", MSG))
    with pytest.raises(FeatureNotAllowed):
        gw.handle(GatewayRequest("br-ben-song", "weekly_report_agent", MSG))
    assert gw.sink.records == []


def test_skeleton_has_no_retry_error_propagates():
    gw = Gateway([provider(faults={"error_500": 1.0})])
    with pytest.raises(ProviderError) as e:
        gw.handle(GatewayRequest("br-cau-go", "chat", MSG))
    assert e.value.kind == "server_error"


def test_rate_limit_error_carries_retry_after():
    gw = Gateway([provider(faults={"rate_limit": 1.0}, retry_after_s=4)])
    with pytest.raises(ProviderError) as e:
        gw.handle(GatewayRequest("br-cau-go", "chat", MSG))
    assert e.value.kind == "rate_limit" and e.value.retry_after == 4.0


def test_extension_by_subclass_without_editing_core():
    class Counting(Gateway):
        calls = 0

        def before_call(self, req, tenant):
            Counting.calls += 1
            super().before_call(req, tenant)

    gw = Counting([provider()])
    gw.handle(GatewayRequest("br-cau-go", "chat", MSG, output_tokens=3))
    assert Counting.calls == 1


def test_stream_helper_reports_ttft_before_total():
    pr = provider()
    items = list(pr.stream("fake-small", MSG, output_tokens=8))
    result = items[-1][1]
    assert result.output_tokens == 8 and result.ttft_s <= result.total_s
    assert "".join(x[1] for x in items[:-1]).split().__len__() == 8
