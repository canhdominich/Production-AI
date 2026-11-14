import contextlib
import contextvars
import json
import logging
import re
import secrets
import unicodedata
from datetime import datetime, timezone

trace_var = contextvars.ContextVar("trace", default=None)

TRACEPARENT = re.compile(r"^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")
OWN_KEYS = {"ts", "level", "service", "trace_id", "span_id", "request_id"}
DENY_KEYS = {"message", "prompt", "answer", "address", "phone", "authorization"}
RESERVED = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}

PLACE_WORDS = ("hoa sen man trang non lua vang sao mai duong mia ca ro che xanh dua xiem cau go xom vui "
               "ben song bai bien cho moi doi thong dau pho khu cong nghiep").split()


def fold(text):
    return "".join("d" if ch == "đ" else "D" if ch == "Đ" else unicodedata.normalize("NFD", ch)[0] for ch in text)


def new_traceparent(sampled=True):
    return f"00-{secrets.token_hex(16)}-{secrets.token_hex(8)}-{'01' if sampled else '00'}"


def parse_traceparent(header):
    m = TRACEPARENT.match(header or "")
    if not m:
        return None
    version, trace_id, parent_id, flags = m.groups()
    if version == "ff" or set(trace_id) == {"0"} or set(parent_id) == {"0"}:
        return None
    return {"version": version, "trace_id": trace_id, "parent_id": parent_id, "flags": flags}


def child_traceparent(header):
    parsed = parse_traceparent(header)
    if parsed is None:
        return new_traceparent()
    return f"00-{parsed['trace_id']}-{secrets.token_hex(8)}-{parsed['flags']}"


PHONE = re.compile(r"(?<![\w.,/+-])(?:(?:\(\+84\)|\+84|84)[ .-]?|0)[35789](?:[ .-]?\d){8}(?!\d)")
_W = "|".join(PLACE_WORDS)
PLACE = rf"(?:{_W})\b(?:\s+(?:{_W})\b){{0,3}}"
NUM = r"\d{1,4}[a-z]?(?!\d)"
KEYSEG = (rf"(?:(?:ngo|ngach|hem|kiet|thon|huyen|duong|phuong|quan|pho|tp\.|p\.|q\.)\s*(?:{NUM}|{PLACE})"
          rf"|khu\s+pho\s+{NUM}|chung\s+cu\s+(?:{PLACE})|toa\s+[a-z]\b|can\s+\d{{3,4}}(?!\d))")
HOUSE = rf"so\s+{NUM}(?:[/-]{NUM})*"
SLASH = rf"{NUM}(?:[/-]{NUM})+\s+(?={PLACE})"
SEP = r"(?:\s*,\s*|\s+)"
ELEM = rf"(?:{HOUSE}(?={SEP}{KEYSEG})|{SLASH}{PLACE}|{KEYSEG})"
ADDRESS = re.compile(rf"(?<![\w/.]){ELEM}(?:{SEP}(?:{ELEM}|{PLACE}))*")


def redact_phone(text):
    return PHONE.sub("[phone]", text)


def redact_address(text):
    out, pos = [], 0
    for m in ADDRESS.finditer(fold(text).lower()):
        out += [text[pos:m.start()], "[address]"]
        pos = m.end()
    return "".join(out) + text[pos:]


def redact_text(text):
    return redact_address(redact_phone(text))


def redact_value(value, key=""):
    if key in OWN_KEYS:
        return value
    if key in DENY_KEYS:
        return "[removed]"
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: redact_value(v, k) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_value(v) for v in value]
    return value


class JsonFormatter(logging.Formatter):
    def __init__(self, service):
        super().__init__()
        self.service = service

    def format(self, record):
        data = {"ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
                "level": record.levelname, "service": self.service, "event": record.getMessage()}
        ids = trace_var.get()
        if ids:
            data["trace_id"], data["span_id"] = ids["trace_id"], ids["span_id"]
        data.update({k: v for k, v in record.__dict__.items() if k not in RESERVED})
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(redact_value(data), ensure_ascii=False, default=str)


def make_logger(name, service, stream):
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter(service))
    log = logging.getLogger(name)
    log.handlers[:] = [handler]
    log.setLevel(logging.INFO)
    log.propagate = False
    return log


@contextlib.contextmanager
def bind(header):
    parsed = parse_traceparent(child_traceparent(header))
    token = trace_var.set({"trace_id": parsed["trace_id"], "span_id": parsed["parent_id"], "flags": parsed["flags"]})
    try:
        yield trace_var.get()
    finally:
        trace_var.reset(token)


def current_traceparent():
    ids = trace_var.get()
    return f"00-{ids['trace_id']}-{ids['span_id']}-{ids['flags']}"


def find_leaks(lines, secrets_):
    def squash(s):
        return re.sub(r"[\s.\-()+]", "", s)

    leaked = set()
    for secret in secrets_:
        digits = squash(secret)
        numeric = digits.isdigit() and len(digits) >= 9
        for line in lines:
            if secret in line or (numeric and digits in squash(line)):
                leaked.add(secret)
                break
    return sorted(leaked)
