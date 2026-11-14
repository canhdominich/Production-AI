import collections
import io

import _data
import _jsonlog

records = _data.load()
sink = io.StringIO()
log = _jsonlog.make_logger("naive", "api", sink, redact=False)


def handle_chat(rec):
    text = rec["text"]
    log.info("chat request: " + text)
    log.info("provider_request", extra={"body": {"messages": [{"role": "user", "content": text}]}})
    if int(rec["id"][1:]) % 6 == 0:
        try:
            raise ValueError(f"cannot match delivery note for: {text}")
        except ValueError:
            log.exception("order_lookup_failed")


for rec in records:
    handle_chat(rec)

secrets = _data.secrets_of(records)
by_channel = collections.Counter()
exposed = set()
lines = sink.getvalue().splitlines()
for line in lines:
    hits = [s for s in secrets if s in line]
    if hits:
        channel = "message text" if '"event": "chat request' in line else "extra body" if "provider_request" in line else "exception text"
        by_channel[channel] += 1
        exposed.update(hits)

print(f"messages replayed          : {len(records)}")
print(f"log lines written          : {len(lines)}")
print(f"lines with phone or address: {sum(by_channel.values())}")
for channel, n in by_channel.most_common():
    print(f"  {channel:<14} {n:>4} lines")
print(f"distinct values exposed    : {len(exposed)} of {len(set(secrets))}")
