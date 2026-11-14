import json

from _kit import STACK

DASHBOARD_PATH = STACK / "grafana" / "anhti-llm.dashboard.json"
DS = {"type": "prometheus", "uid": "prom-local"}

PANELS = [
    ("Request rate by feature", 'sum by (feature) (rate(llm_requests_total[5m]))', "reqps", 12),
    ("Error ratio, 5 min window", "llm:error_ratio_rate5m", "percentunit", 12),
    ("p95 latency by feature", "histogram_quantile(0.95, sum by (le, feature) (rate(llm_request_duration_seconds_bucket[5m])))", "s", 12),
    ("Answers cut at max_tokens", 'sum(rate(llm_finish_total{reason="length"}[15m])) / sum(rate(llm_finish_total[15m]))', "percentunit", 12),
    ("Cost per hour by tenant", "sum by (tenant) (increase(llm_cost_usd_total[1h]))", "currencyUSD", 12),
    ("Sampled pass rate, 3 days", 'sum(increase(llm_eval_samples_total{verdict="pass"}[3d])) / sum(increase(llm_eval_samples_total[3d]))', "percentunit", 12),
    ("Burn rate, 1 hour window", "llm:error_ratio_rate1h / 0.005", "none", 12),
    ("Input drift (PSI)", "max by (feature) (llm_input_psi)", "none", 12),
]


def build(panels=PANELS):
    out = []
    for i, (title, expr, unit, width) in enumerate(panels):
        out.append({"id": i + 1, "type": "timeseries", "title": title, "datasource": DS,
                    "gridPos": {"h": 8, "w": width, "x": (i % 2) * 12, "y": (i // 2) * 8},
                    "fieldConfig": {"defaults": {"unit": unit}, "overrides": []},
                    "targets": [{"refId": "A", "datasource": DS, "expr": expr, "legendFormat": "{{feature}}" if "feature" in expr else ""}]})
    return {"uid": "anhti-llm-prod", "title": "Giao Hang Anh Ti: AI service in production", "schemaVersion": 42, "version": 1,
            "tags": ["anhti", "llm", "slo"], "time": {"from": "now-6h", "to": "now"}, "refresh": "1m", "panels": out}


def write(dash):
    DASHBOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_PATH.write_text(json.dumps(dash, indent=2, ensure_ascii=False), encoding="utf-8")
