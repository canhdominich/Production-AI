import hashlib
import math
import re

DEFAULT_RULES = (
    ("page", "1h", "5m", 14.4),
    ("page", "6h", "30m", 6.0),
    ("ticket", "1d", "2h", 3.0),
    ("ticket", "3d", "6h", 1.0),
)


def should_sample(request_id, rate, salt="eval-v1"):
    # Băm id thành số trong [0, 1): mọi bản sao của dịch vụ cho cùng kết quả
    digest = hashlib.sha256(f"{salt}:{request_id}".encode()).hexdigest()
    return int(digest[:8], 16) / 2**32 < rate


def weighted_pass_rate(samples):
    # samples: danh sách (passed, inclusion_probability); trọng số là 1 chia xác suất được chọn
    if not samples:
        raise ValueError("no samples")
    weights = [1 / p for _, p in samples]
    return sum(w for (passed, _), w in zip(samples, weights) if passed) / sum(weights)


def wilson_interval(passes, n, z=1.96):
    if n == 0:
        return 0.0, 1.0
    p = passes / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)


def corrected_pass_rate(measured, tpr, tnr):
    if tpr + tnr <= 1:
        raise ValueError("judge is no better than a coin flip")
    value = (measured + tnr - 1) / (tpr + tnr - 1)
    return min(1.0, max(0.0, value))


def psi(expected, actual, eps=1e-4):
    e_total, a_total = sum(expected), sum(actual)
    score = 0.0
    for e, a in zip(expected, actual):
        pe, pa = max(e / e_total, eps), max(a / a_total, eps)
        score += (pa - pe) * math.log(pa / pe)
    return score


def burn_rate(errors, total, slo):
    if total == 0:
        return 0.0
    return (errors / total) / (1 - slo)


def burn_alert(ratios, slo, rules=DEFAULT_RULES):
    # ratios: {"1h": 0.09, "5m": 0.2, ...}; một luật chỉ bật khi cả cửa sổ dài và ngắn vượt ngưỡng
    budget = 1 - slo
    found = None
    for severity, long_w, short_w, rate in rules:
        if long_w in ratios and short_w in ratios and ratios[long_w] > rate * budget and ratios[short_w] > rate * budget:
            if severity == "page":
                return "page"
            found = "ticket"
    return found


def dashboard_problems(dash, known_metrics):
    errs = []
    panels = dash.get("panels", [])
    ids = [p.get("id") for p in panels]
    errs += [f"duplicate id {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
    for i, a in enumerate(panels):
        ga = a["gridPos"]
        if ga["x"] + ga["w"] > 24:
            errs.append(f"panel {a['id']} is wider than the 24 column grid")
        for b in panels[i + 1:]:
            gb = b["gridPos"]
            if ga["x"] < gb["x"] + gb["w"] and gb["x"] < ga["x"] + ga["w"] and ga["y"] < gb["y"] + gb["h"] and gb["y"] < ga["y"] + ga["h"]:
                errs.append(f"panels {a['id']} and {b['id']} overlap")
    for p in panels:
        targets = p.get("targets", [])
        if not targets:
            errs.append(f"panel {p['id']} has no query")
        for name in sorted({n for t in targets for n in re.findall(r"\b(llm[a-z0-9_:]*)", t["expr"])}):
            if name not in known_metrics:
                errs.append(f"panel {p['id']} uses unknown metric {name}")
    return errs
