# Trade Logistics Management

International Freight & Customs Clearance service, built as a **modular
monolith** with three modules:

| Module              | Schema     | Responsibility                                        |
| ------------------- | ---------- | ----------------------------------------------------- |
| `shipment`          | `shipment` | Cargo lifecycle, routing and transport readiness       |
| `customs_clearance` | `customs`  | Regulatory compliance state machine (duty, documents)  |
| `files`             | `files`    | Storing files across storage classes, behind one interface |

Modules share only the `modules/shared` kernel and never import one another.
`shipment` and `customs_clearance` talk exclusively through integration events
(outbox/inbox over RabbitMQ); `files` is reached over HTTP and hands back a
`file_uuid`, which is all a caller ever holds. Each module owns its schema, its
migrations and its contract, so any of them could be lifted out into a service
of its own — `files` most readily.

> **Status:** six slices are implemented. Shipment: *create draft shipment*
> (`POST /shipments`), *assign complex route*
> (`PUT /shipments/{shipment_id}/route`) and *finalize cargo manifest*
> (`POST /shipments/{shipment_id}/finalize-manifest`). Customs Clearance:
> *open clearance case*, driven by the `ShipmentManifestFinalized` message
> rather than by HTTP, *attach legal document reference*
> (`POST /customs/cases/{case_id}/documents`) and *verify document*
> (`POST /customs/cases/{case_id}/documents/{document_id}/verify`). Files:
> *upload file* (`POST /files`). The shared message bus (outbox, inbox,
> retries, error queue, both CLI commands) carries the events between the
> modules; the `file_uuid` returned by Files is how a clearance case points at
> a document without either module importing the other.

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
  the error queue with an `exception_details` header naming the exception and
  when it failed, and an `endpoint` header saying whose it was and how to put
  it back. It goes there through the direct exchange as well: a poison message has
  exactly one destination, so there is nothing to fan out to.

A dead-lettered message keeps its own id, type and body, so replaying it is a
republish rather than a reconstruction. The `endpoint` header carries where to
republish it:

```json
{
  "name": "customs-worker",
  "delivery_metadata": {
    "message_type": "trade-logistics.shipment.shipment-manifest-finalized",
    "exchange": "trade-logistics.direct",
    "routing_key": "trade-logistics.customs.retry"
  }
}
```

`name` is the endpoint that failed it — `--app-name`, the same value the retry
path records in its `retry_endpoint` header, so one message never names its
endpoint two different ways. The exchange and routing key are
deliberately the **retry queue's own dead-letter pair**, not the exchange the
message first arrived on: that pair is the way into this consumer's queue, so
a replay service reading the error queue can republish to it and the message
lands back where it failed instead of fanning out to every subscriber of the
original topic.

The broker therefore carries two exchanges and no more. **`trade-logistics.topic`**
publishes integration events, where a module announces something and any number
of consumers may care. **`trade-logistics.direct`** handles everything addressed
at exactly one queue: a retry going back to the consumer that failed it, and a
poison message going to the error queue.

Each module owns `outbox_messages` and `inbox_messages` inside its own schema.
The tables are declared once and resolved per worker through SQLAlchemy's
`schema_translate_map`, so there is a single mapping and two physical tables.

### How a retry finds its way back

A retry must return to the queue it failed on and to nothing else. Sending it
back to the primary **topic** exchange would hand it to every queue bound to
that pattern, waking sibling modules with work they never attempted. So the
return trip goes through a **direct** exchange under a key that names the
failing queue, and the primary queue carries a second binding for it:

```
                 topic  trade-logistics.topic
                   │ trade-logistics.shipment.#
                   ▼
        ┌── trade-logistics.customs ──┐          handler raises
        │      (primary queue)        │──────────────┐
        └─────────────────────────────┘              ▼
                   ▲                        direct  trade-logistics.direct
                   │                                 │ ….customs.delayed-retry
                   │                                 ▼
                   │                     trade-logistics.customs.delayed-retry
                   │  bind: ….customs.retry           (TTL 10s, then expires)
                   └──────────────◀──────────────────┘
                     x-dead-letter-routing-key
                        ….customs.retry
```

The direct exchange is named for its type, not for retries: both hops across it
address exactly one queue, and anything else needing point-to-point routing
belongs there too.

Both keys are derived from the primary queue name, so two workers never share
one — `trade-logistics.customs.retry` and `trade-logistics.shipment.retry` are
different keys on a direct exchange. All four parts are overridable:
`--retry-queue-dead-letter-exchange`, `--retry-queue-dead-letter-routing-key`,
`--primary-queue-retry-binding-exchange` and `--primary-queue-retry-binding-key`.
The dead-letter key and the second binding key must match — that is the join.

Name a retry queue `…delayed-retry` rather than `…retry`, so it reads
differently from the `….retry` key an expired message comes back under.

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
  --retry-queue trade-logistics.customs.delayed-retry \
  --retry-queue-binding-key trade-logistics.customs.delayed-retry \
  --retry-queue-message-ttl 10000 \
  --immediate-retries-number 3 \
  --delayed-retries-number 3 \
  --app-name customs-clearance

docker compose exec app python worker.py handle-messages --help   # all flags
```

Every flag spelled out, for when a deployment shares nothing with the defaults:

```bash
docker compose exec app python worker.py handle-messages \
  --module customs_clearance \
  --limit 10 \
  --primary-queue trade-logistics.customs \
  --primary-queue-binding-key 'trade-logistics.shipment.#' \
  --primary-queue-exchange trade-logistics.topic \
  --primary-queue-exchange-type topic \
  --primary-queue-retry-binding-exchange trade-logistics.direct \
  --primary-queue-retry-binding-key trade-logistics.customs.retry \
  --retry-queue trade-logistics.customs.delayed-retry \
  --retry-queue-binding-key trade-logistics.customs.delayed-retry \
  --retry-queue-exchange trade-logistics.direct \
  --retry-queue-exchange-type direct \
  --retry-queue-message-ttl 10000 \
  --retry-queue-dead-letter-exchange trade-logistics.direct \
  --retry-queue-dead-letter-routing-key trade-logistics.customs.retry \
  --immediate-retries-number 3 \
  --delayed-retries-number 3 \
  --error-queue trade-logistics.error \
  --error-queue-exchange trade-logistics.direct \
  --error-queue-exchange-type direct \
  --error-queue-routing-key trade-logistics.dead-letter \
  --app-name customs-clearance
```

Reading it as three groups makes it shorter than it looks:

| Group | Flags | What it decides |
| ----- | ----- | --------------- |
| Intake | `--primary-queue*` | Which queue this worker drains, and what the topic exchange routes into it |
| Retry | `--retry-queue*`, `--*-retries-number` | Where a failure waits, for how long, and how it gets back — the two `…retry-binding…` flags and the two `…dead-letter…` flags are the two ends of one hop and must agree |
| Failure | `--error-queue*` | Where a message lands once the delayed retries are spent |

`--module` is the only required flag. Everything else falls back to the
environment, and the four return-path flags fall back to the primary queue
name, so the concise form above produces exactly this topology.

The dispatcher takes far fewer, since publishing needs no queues:

```bash
docker compose exec app python worker.py dispatch-messages \
  --module customs_clearance \
  --limit 50 \
  --primary-queue-exchange trade-logistics.topic \
  --primary-queue-exchange-type topic \
  --app-name customs-clearance
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

## Files

`modules/files` stores files across storage classes behind one interface. A
caller names a **disk** and a path; it gets back a `file_uuid` and never learns
which backend holds the bytes.

```bash
curl -X POST http://localhost:8000/files \
  -F "file=@commercial_invoice.pdf;type=application/pdf" \
  -F "disk=local" \
  -F "path=customs/clearance-cases" \
  -F "name=commercial_invoice.pdf" \
  -F 'metadata={"issued_by":"ACME Freight"}' \
  -F 'references=[{"context":"customs","entity_type":"ClearanceCase",
                   "entity_id":1,
                   "uuid":"f9502c94-7aff-4290-a269-0443423c0d1e"}]'
```

The request is `multipart/form-data` because it carries bytes as well as JSON:
`metadata` and `references` are JSON documents in their own form parts.

### References

A reference says what the file is about. The whole array is **optional** — the
client decides whether the file relates to anything at all.

| Field         | Required | Meaning                                            |
| ------------- | -------- | -------------------------------------------------- |
| `context`     | yes      | Bounded context the file relates to, e.g. `customs` |
| `entity_type` | yes      | Kind of thing it is about, e.g. `ClearanceCase`     |
| `entity_id`   | no       | Primary key of that entity, when it has one         |
| `uuid`        | no       | UUID of that entity, when it has one                |

Both identifiers are optional because what a file is about is not always an
aggregate with a row of its own: a reference can describe an external entity
that has files but no identifier here.

`id` is **not** part of the request. It is the key of the reference record
itself, assigned by the database and returned in the response; a client that
sends one is refused with a `422` rather than quietly ignored.

### Disks

A disk is a name bound to a backend and its credentials. `local` always exists;
a cloud disk becomes selectable once its bucket or host is set in `.env`, so an
unconfigured backend is refused up front instead of failing mid-upload.

| Disk    | Backend                       | Driver, installed per deployment |
| ------- | ----------------------------- | -------------------------------- |
| `local` | directory in the container    | built in                         |
| `gcp`   | Google Cloud Storage bucket   | `pip install ".[gcp]"`           |
| `aws`   | S3 bucket, or an S3-compatible endpoint | `pip install ".[aws]"` |
| `sftp`  | remote SFTP server            | `pip install ".[sftp]"`          |

The `local` disk is a mount, not part of the image: Compose backs
`FILES_LOCAL_ROOT` with the `files-data` volume, and the `files-storage-init`
service hands it to the non-root user the app runs as before the app starts. On
Kubernetes that job belongs to the PVC's pod — an init container, or
`securityContext.fsGroup` — and the image stays out of it either way.

Everything else the module needs is in `.env` — see the `FILES_*` block in
[`.env.example`](.env.example). Cloud credentials are read from a path
(`FILES_GCP_CREDENTIALS_PATH`) or from the environment, so key files are
mounted rather than baked into the image. Leaving the AWS key pair empty falls
back to the standard credential chain (instance role, `~/.aws`, `AWS_*`).

### What it guarantees

- **The record describes reality.** Size and checksum are measured from what
  was actually written, never taken from the client.
- **An upload cannot escape its disk.** `..`, absolute paths and separators in
  the file name are refused by the storage location value object.
- **No orphan `file_uuid`.** The bytes are written before the row, and the
  object is removed again if the row cannot be inserted.
- **No silent overwrite.** A second upload to the same key answers `409`.

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
  (the Files module publishes
  [`modules/files/openapi.yaml`](modules/files/openapi.yaml))
- [`modules/*/asyncapi.yaml`](modules) — integration message contracts
