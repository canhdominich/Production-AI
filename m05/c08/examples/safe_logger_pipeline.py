import hashlib
import hmac
import io

import _data
import _jsonlog
import _redactkit

records = _data.load()
SECRET_KEY = b"demo-key-rotate-me"
phones = _data.secrets_of(records, ("phone",))
addresses = _data.secrets_of(records, ("address",))
names = _data.secrets_of(records, ("name",))


def fingerprint(value):
    return hmac.new(SECRET_KEY, value.encode(), hashlib.sha256).hexdigest()[:12]


def handle(log, rec, mode):
    text = rec["text"]
    shown = _redactkit.redact(text) if mode == "call_site" else text
    if mode == "allowlist":
        log.info("chat_request", extra={"text_len": len(text), "text_fp": fingerprint(text), "pii_kinds": sorted({s["kind"] for s in rec["pii"]})})
    else:
        log.info("chat request: " + shown)
        log.info("provider_request", extra={"body": {"messages": [{"role": "user", "content": text}]}})
    if int(rec["id"][1:]) % 6 == 0:
        try:
            raise ValueError("cannot match delivery note for: " + (text if mode != "allowlist" else f"<{len(text)} chars>"))
        except ValueError:
            log.exception("order_lookup_failed")


def run(mode, redact):
    sink = io.StringIO()
    log = _jsonlog.make_logger(mode, "api", sink, redact=redact)
    for rec in records:
        handle(log, rec, mode)
    return sink.getvalue()


def leaks(output, values):
    unique = set(values)
    return sum(1 for line in output.splitlines() if any(v in line for v in unique))


print(f"{'configuration':<34}{'phone':>7}{'address':>9}{'name':>6}   (log lines that contain a value)")
for label, mode, redact in [("1 no protection", "naive", False), ("2 redact at call site only", "call_site", False),
                            ("3 redact in the formatter", "naive", True), ("4 formatter + log nothing extra", "allowlist", True)]:
    out = run(mode, redact)
    print(f"{label:<34}{leaks(out, phones):>7}{leaks(out, addresses):>9}{leaks(out, names):>6}")
print("one line of configuration 4:", run("allowlist", True).splitlines()[0][-110:])
