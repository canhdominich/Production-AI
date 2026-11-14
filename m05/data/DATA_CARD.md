# Data card: m05 shared platform base (simulated)

Everything here is synthetic. The base exists so that every chapter of m05 measures the same system with the same traffic, the same tenants and the same price list. It is frozen: do not edit it, extend it from your own chapter folder. `platform/tests/test_frozen.py` checks the SHA-256 of every frozen file.

## What is synthetic

| Item | Real or invented | Notes |
|---|---|---|
| Branches, budgets, rate limits, API keys | invented | 5 branches named after districts of the fictional city Phố Rôm Rả. Keys such as `demo-key-cau-go` are teaching strings and must never be reused anywhere real |
| Prices in `prices.json` | invented | `illustrative: true`. They are NOT the price list of any real vendor. Replace them with the official numbers (with the access date) before any real budget decision; the file explains how |
| Model names `fake-small`, `fake-medium`, `fake-large` | invented | tier aliases; a real deployment maps them to real models |
| Latency of the fake provider | invented | `ttft = (base + per_token * prompt_tokens) * jitter`, `tpot` per tier, log-normal jitter (sigma 0.15). The shape is typical of hosted LLMs, the absolute numbers are not measurements of any product |
| Text produced by the fake provider | invented | random Vietnamese words from a fixed list; it carries no meaning. Never judge answer quality with it |
| Token counts | estimated | `ceil(characters / 3.2)` plus 4 per message; not a real tokenizer. Real counts differ by model and language |
| Request texts | reused | customer messages from `lab/m02/data/messages.csv`, questions from `lab/m03/data/questions.csv`, policy paragraphs from `lab/m04/data/policy.md`, complaint cases from `lab/m04/data/cases.csv` (all frozen, all synthetic) |
| Output lengths | simulated | log-normal per feature (chat median 120, knowledge assistant 240, weekly report 1400 tokens), clipped; see `workload.FEATURE_SPEC` |

## Workload rules

`workload.generate(n, seed=42)` is deterministic: the same seed gives the same list byte for byte. Shares: 70% chat, 27% knowledge assistant, 3% weekly report agent. Tenants are drawn by `traffic_share` among tenants that have the feature (Bến Sông has no weekly report). Users are drawn among roles that may use the feature. Arrival times follow a day curve with peaks at 11 to 13 h and 17 to 19 h; weekly reports arrive between 6 and 9 h. The 4-step weekly report agent is one request with `steps = 4`; the caller decides whether to send the steps as one call or four.

## Fake provider rules

- Deterministic by `(seed, x-fake-request-id, attempt)`: text, jitter and faults. Without a request id the order of arrival decides, so use the header when you run requests concurrently.
- `x-fake-output-tokens` sets how many tokens the "model" wants to say; `max_tokens` can truncate it (`finish_reason: length`). Without the header the length comes from a hash of the prompt (median about 150).
- Faults: `rate_limit` (429 with `Retry-After`), `error_500`, `timeout` (hangs `timeout_hang_s`, then 504), `slow` (latency times `slow_factor`), `cut` (stream stops after a third of the tokens). Probabilities are set per kind and must sum to at most 1. A retry of the same request id draws a new decision.
- `capacity`: when the number of in-flight requests exceeds it, new requests get a natural 429.
- Load effect: above `knee` concurrent requests the per-token time grows by `load_factor` per extra knee; a crude stand-in for a saturated GPU.
- `time_scale` multiplies all sleeps. Chapters that use a scale below 1 must say so and convert back when they quote seconds.

## Quirks and honesty

- A model call here is a sleep, not computation: CPU use is tiny, so a load test against the fake provider measures your code, not any model.
- Streaming cancellation: when a streaming client disconnects the fake provider stops generating and counts only the tokens already sent; a non-streaming request still finishes and is counted in full. Real providers differ and their documentation must be checked.
- Costs computed from `prices.json` are consistent inside the lab but say nothing about real spend.
- Names in `tenants.json` users (An, Bình, Lan, Minh, Hà) are written without diacritics for code safety.
