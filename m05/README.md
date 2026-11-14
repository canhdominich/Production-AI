# m05: Production AI Engineering lab

Lab code of the course "Production AI: Triển khai, giám sát và tối ưu chi phí dịch vụ AI". One chapter per folder (`c01` to `c15`), one shared platform base in `data/` and `platform/` that is **frozen**: later chapters read it, import it and extend it from their own folder, but never edit it. Read `data/DATA_CARD.md` before using it.

The scenario: Giao Hàng Anh Tí opens the chat (m02), the knowledge assistant (m03) and the operations agent (m04) to 5 branches (tenants), each with its own budget, rate limit and permitted features. Everything runs on one VM.

## One system, one set of names

Every lesson of m05 draws the same service architecture. Use these node names in Mermaid diagrams, code and prose so the system visibly grows from chapter to chapter.

| Node id | Label in diagrams | What it is | Built in |
|---|---|---|---|
| `Caddy` | Caddy | reverse proxy: HTTPS, timeouts, request size limit | c01 (drawn), c04 and c05 (built) |
| `API` | API | FastAPI app: authentication, tenant and role, request validation, streaming to the client | c01 (drawn), c11, c15 |
| `Gateway` | AI Gateway | the single door for every model call: limits, usage records, cost, retry, fallback | c01 (skeleton), c10, c11, c13 |
| `Worker` | Worker | background jobs (weekly report agent, batch work) taken from a queue | c01 (drawn), c13, c15 |
| `PostgreSQL` | PostgreSQL | tenants, usage_events, jobs, audit log, chat history, pgvector for the knowledge assistant | c01 (drawn), c10, c12 |
| `Redis` | Redis | rate-limit counters, cache, job queue | c01 (drawn), c09, c10, c13 |
| `Provider` | Model provider | a hosted API, vLLM or Ollama; in this base the fake provider `platform/fake_provider.py` | c01 (fake), c02, c03, c06 |
| `Observability` | Observability | traces, metrics, logs, dashboards, alerts | c07, c08, c14 |

Flows, always drawn in this order:

- **Request flow** (online): user, `Caddy`, `API`, `Gateway`, `Provider`, and the answer back up the same path. Streaming keeps the connection open from `Provider` to the user.
- **Job flow** (background): `API` writes a job to `PostgreSQL` and `Redis`, `Worker` takes it, calls `Gateway`, writes the result to `PostgreSQL`; the user polls `API`.
- **Side flows**: every node reports to `Observability`; `Gateway` writes usage records to `PostgreSQL`.

Colors in Mermaid follow `docs/MERMAID-STANDARD.md`: `main` for the part a lesson teaches, `input` for data stores, `process` for parts of other chapters, `success` for results, `decision` for choices, `error` for the failure being studied.

## Chapter map

| Chapter | Topic | Adds to the system |
|---|---|---|
| c01 | Kiến trúc hệ thống AI | C4 container diagram, sync / streaming / job choice, gateway skeleton extended into a usage-recording gateway |
| c02 | Model serving | `Provider` becomes vLLM or Ollama behind the same OpenAI-compatible interface |
| c03 | Tối ưu inference | TTFT, TPOT, throughput, batching measured against `Provider` |
| c04 | Docker cho ứng dụng AI | `Caddy`, `API`, `Gateway`, `Worker`, `PostgreSQL`, `Redis` as a Compose stack |
| c05 | Triển khai lên cloud | the same stack on a VM with HTTPS |
| c06 | Hạ tầng GPU | GPU capacity and cost for `Provider` (concepts) |
| c07 | AI observability | `Observability`: metrics, quality signals |
| c08 | Logging và tracing | `Observability`: structured logs, end-to-end traces |
| c09 | Tối ưu hiệu năng | caching in `Redis`, concurrency in `API` and `Gateway` |
| c10 | Tối ưu chi phí | budgets per tenant, model routing, cost dashboards |
| c11 | Bảo mật và quyền riêng tư | authentication, authorisation, PII masking, audit |
| c12 | Quản trị AI | governance, prompt and model versioning, approvals |
| c13 | Reliability engineering | retry, fallback, circuit breaker, chaos tests with the fault injector |
| c14 | Giám sát production | SLOs, alerts, runbooks |
| c15 | Dự án cuối khóa | everything together, deployable |

## Conventions for every chapter

- Folder `lab/m05/cNN/` with `examples/`, and `lab/{starter,solution,tests}/` for the chapter lab. Never touch another chapter's folder.
- PostgreSQL: container `anhti-pg` on `localhost:55432` (user, password, database all `anhti`), your own schema `m05_cNN`.
- Docker Compose project name `m05_cNN`. Ports: base `5600 + chapter number * 10` (c01 uses 5610 to 5619, c02 uses 5620 to 5629, and so on). Clean up your containers when done.
- Import the base by putting `lab/m05/platform` on `sys.path`; do not add `__init__.py` there (a folder named `platform` with an init file would shadow the standard library module):

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "platform"))
from gateway_core import Gateway, GatewayRequest, ProviderClient
from workload import generate
```

- Start the fake provider: `python platform/fake_provider.py --port 5610`, or in code `fake_provider.create_app(Config(...))` served by `uvicorn`. Environment: `FAKE_SEED`, `FAKE_TIME_SCALE` (0.1 means ten times faster than the model's real pace), `FAKE_FAULTS` (JSON such as `{"rate_limit": 0.2}`). Admin: `GET/POST /admin/config`, `GET /admin/stats`, `POST /admin/reset`.
- Run the base tests: `uv run --project lab python -m pytest lab/m05/platform/tests`.

## What the base gives you

| File | Purpose |
|---|---|
| `data/tenants.json` | 5 branches with monthly budget, rate limit, plan, allowed features, maximum model tier, roles and sample users |
| `data/prices.json` | an invented price table for three model tiers (`fake-small`, `fake-medium`, `fake-large`), marked illustrative, with instructions for replacing it |
| `platform/common.py` | token estimate, percentile, paths |
| `platform/workload.py` | `generate(n, seed=42)`: requests for chat, knowledge assistant and weekly report agent with long-tailed lengths |
| `platform/fake_provider.py` | OpenAI-compatible server (Chat Completions and Responses, streaming, usage) with a latency model and fault injection |
| `platform/gateway_core.py` | gateway skeleton: `ProviderClient`, `UsageRecord`, `TenantRegistry`, `PriceTable`, `Gateway` with extension hooks |
| `platform/tests/` | 43 tests of the base; `test_frozen.py` fails if a frozen file changes or a new file appears in `data` or `platform`; `FROZEN.sha256` lists the checksums |
