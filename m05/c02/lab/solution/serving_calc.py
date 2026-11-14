HOURS_PER_MONTH = 730


def resolve_endpoint(profiles, name, env):
    cfg = profiles[name]
    base_url = env.get("CHAT_BASE_URL", cfg["base_url"]).rstrip("/")
    if not base_url.endswith("/v1"):
        raise ValueError(f"base_url must end with /v1: {base_url}")
    return {
        "base_url": base_url,
        "model": env.get("CHAT_MODEL", cfg["model"]),
        "api_key": env.get("CHAT_API_KEY", cfg["api_key"]),
        "extra": dict(cfg.get("extra", {})),
    }


def api_cost_per_request(price, avg_in, avg_out):
    return (avg_in * price["input_per_mtok"] + avg_out * price["output_per_mtok"]) / 1_000_000


def selfhost_fixed_cost(gpu_per_hour, gpus, ops_per_month, hours=HOURS_PER_MONTH):
    return gpu_per_hour * gpus * hours + ops_per_month


def breakeven_requests(fixed_cost, per_request_api):
    if per_request_api <= 0:
        raise ValueError("per_request_api must be positive")
    return fixed_cost / per_request_api


def required_utilization(requests_per_month, avg_out, tokens_per_second, gpus, hours=HOURS_PER_MONTH):
    capacity = tokens_per_second * gpus * hours * 3600
    return requests_per_month * avg_out / capacity


def decide(requests_per_month, per_request_api, fixed_cost, utilization, max_utilization=0.6):
    if requests_per_month * per_request_api <= fixed_cost:
        return "api"
    if utilization <= max_utilization:
        return "self-host"
    return "self-host-needs-more-gpus"
