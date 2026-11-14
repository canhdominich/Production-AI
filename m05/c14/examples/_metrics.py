from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

registry = CollectorRegistry()
REQUESTS = Counter("llm_requests_total", "Requests handled by the AI Gateway", ["feature", "status"], registry=registry)
LATENCY = Histogram("llm_request_duration_seconds", "Gateway call duration", ["feature"], registry=registry,
                    buckets=(0.5, 1, 2.5, 5, 10, 30))
FINISH = Counter("llm_finish_total", "Finish reasons of model answers", ["feature", "reason"], registry=registry)
COST = Counter("llm_cost_usd_total", "Cost computed from the price table", ["tenant"], registry=registry)
EVAL = Counter("llm_eval_samples_total", "Sampled answers judged online", ["feature", "verdict"], registry=registry)
PSI = Gauge("llm_input_psi", "Population stability index of the question mix against the reference week", ["feature"], registry=registry)


SUFFIXES = {"counter": ("_total",), "histogram": ("_bucket", "_sum", "_count"), "gauge": ("",)}


def exposed_names():
    names = set()
    for family in registry.collect():
        names.update(family.name + suffix for suffix in SUFFIXES[family.type])
    return names
