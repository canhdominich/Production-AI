import contextvars
import json
import logging
from datetime import datetime, timezone

import _redactkit

trace_var = contextvars.ContextVar("trace_ids", default=None)
OWN_KEYS = {"ts", "level", "service", "trace_id", "span_id", "request_id", "parent_span_id"}
DENY_KEYS = {"message", "prompt", "answer", "address", "phone", "authorization"}
RESERVED = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}


def current_ids():
    return trace_var.get() or {}


def clean(value, key=""):
    if key in OWN_KEYS:
        return value
    if key in DENY_KEYS:
        return "[removed]"
    if isinstance(value, str):
        return _redactkit.redact(value)
    if isinstance(value, dict):
        return {k: clean(v, k) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    return value


class JsonFormatter(logging.Formatter):
    def __init__(self, service, redact=True, ids=current_ids):
        super().__init__()
        self.service, self.redact, self.ids = service, redact, ids

    def format(self, record):
        data = {"ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
                "level": record.levelname, "service": self.service, "event": record.getMessage(), **self.ids()}
        data.update({k: v for k, v in record.__dict__.items() if k not in RESERVED})
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(clean(data) if self.redact else data, ensure_ascii=False, default=str)


def make_logger(name, service, stream, **kw):
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter(service, **kw))
    log = logging.getLogger(name)
    log.handlers[:] = [handler]
    log.setLevel(logging.INFO)
    log.propagate = False
    return log
