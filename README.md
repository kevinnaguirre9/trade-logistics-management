# Trade Logistics Management

International Freight & Customs Clearance service, built as a **modular
monolith** with two bounded contexts:

| Module              | Schema     | Responsibility                                        |
| ------------------- | ---------- | ----------------------------------------------------- |
| `shipment`          | `shipment` | Cargo lifecycle, routing and transport readiness       |
| `customs_clearance` | `customs`  | Regulatory compliance state machine (duty, documents)  |

Both modules share only the `modules/shared` kernel and talk to each other
exclusively through integration events (outbox/inbox over RabbitMQ).

> **Status:** four slices are implemented. Shipment: *create draft shipment*
> (`POST /shipments`), *assign complex route*
> (`PUT /shipments/{shipment_id}/route`) and *finalize cargo manifest*
> (`POST /shipments/{shipment_id}/finalize-manifest`). Customs Clearance:
> *open clearance case*, driven by the `ShipmentManifestFinalized` message
> rather than by HTTP. The shared message bus (outbox, inbox, retries, error
> queue, both CLI commands) carries the event between the two modules.

## Quick start

```bash
cp .env.example .env          # then edit the secrets
docker compose up --build
```

| Service     | URL                              |
| ----------- | -------------------------------- |
| API (Swagger) | http://localhost:8000/docs      |
| Health probe  | http://localhost:8000/health    |
| pgAdmin       | http://localhost:5050           |
| RabbitMQ UI   | http://localhost:15672          |
| PostgreSQL    | localhost:5432                  |

## Local development without Docker

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn main:app --reload
```

## Database migrations

Each module owns its migration history under
`modules/<module>/src/infrastructure/database/migrations`.

```bash
alembic revision --autogenerate -m "create shipments table" \
  --version-path modules/shipment/src/infrastructure/database/migrations \
  --branch-label shipment      # --branch-label only on the first revision

alembic upgrade heads
```

## Message bus

Modules never call each other. They exchange integration messages over RabbitMQ
with at-least-once delivery, made safe by an outbox on the way out and an inbox
on the way in.

```
use case ──write──▶ <schema>.outbox_messages ──dispatch-messages──▶ RabbitMQ
                    (same transaction)                                  │
                                                                 handle-messages
                                                                        │
   handler + <schema>.inbox_messages ◀──────────────────────────────────┘
   (same transaction)
```

- **Transactional outbox.** A message is stored in the same transaction as the
  state change that produced it, so nothing is ever published for work that
  rolled back. `dispatch-messages` relays the pending rows and marks them sent.
- **Inbox and idempotency.** A handler's writes and the `(message_id,
  handler_name)` row that records them commit together, so a redelivery finds
  the row and skips the work.
- **Retries.** A failing handler is retried in process
  (`--immediate-retries-number`), then through a TTL retry queue that returns
  the message to the primary queue (`--delayed-retries-number`).
- **Error queue.** Once the delayed retries are spent the message is parked in
  the error queue with an `exception_details` header naming the endpoint, the
  exception and when it failed.

Each module owns `outbox_messages` and `inbox_messages` inside its own schema.
The tables are declared once and resolved per worker through SQLAlchemy's
`schema_translate_map`, so there is a single mapping and two physical tables.

### Running the workers

`worker.py` is the composition root of the workers, the way `main.py` is for the
HTTP API. `--module` selects the schema and the handlers; every other flag
describes the broker topology and falls back to `.env`, so pointing a worker at
a different queue needs a new command line, not a new build.

```bash
# publish whatever the shipment module has queued
docker compose exec app python worker.py dispatch-messages --module shipment --limit 50

# consume the customs queue, with its own retry and error topology
docker compose exec app python worker.py handle-messages \
  --module customs_clearance \
  --primary-queue trade-logistics.customs \
  --primary-queue-binding-key 'trade-logistics.shipment.#' \
  --retry-queue trade-logistics.customs.retry \
  --retry-queue-binding-key trade-logistics.customs.retry \
  --retry-queue-message-ttl 10000 \
  --immediate-retries-number 3 \
  --delayed-retries-number 3 \
  --app-name customs-worker

docker compose exec app python worker.py handle-messages --help   # all flags
```

## Tests

The suite runs in the `dev` build stage, exposed through the `test` compose
profile, so it never ships in the runtime image. It is database-free — domain
unit tests plus endpoint tests that override the handler dependency — so no
service has to be up first.

```bash
# whole suite
docker compose --profile test run --rm test

# a single file
docker compose --profile test run --rm test \
  pytest modules/shipment/test/features/test_create_draft_shipment.py

# a single test, verbose
docker compose --profile test run --rm test pytest -v -k finalize

# with coverage
docker compose --profile test run --rm test \
  pytest --cov=modules --cov-report=term-missing

# linting and formatting, same image
docker compose --profile test run --rm test ruff check .
docker compose --profile test run --rm test ruff format --check .
```

Anything after the service name replaces the default `pytest` command. Source
is bind-mounted, so edits need no rebuild; add `--build` only after changing
dependencies:

```bash
docker compose --profile test run --rm --build test
```

## Quality gates

Inside a local virtualenv (see above), the same checks run directly:

```bash
ruff check .        # PEP 8 + import order + naming
ruff format .
pytest              # unit tests per module + composition-root smoke tests
```

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — styles, patterns and layer rules
- [`docs/project-structure.md`](docs/project-structure.md) — folder-by-folder map
- [`modules/*/openapi.yaml`](modules) — task-based HTTP contracts
- [`modules/*/asyncapi.yaml`](modules) — integration message contracts
