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

> **Status:** five slices are implemented. Shipment: *create draft shipment*
> (`POST /shipments`), *assign complex route*
> (`PUT /shipments/{shipment_id}/route`) and *finalize cargo manifest*
> (`POST /shipments/{shipment_id}/finalize-manifest`). Customs Clearance:
> *open clearance case*, driven by the `ShipmentManifestFinalized` message
> rather than by HTTP. Files: *upload file* (`POST /files`). The shared message
> bus (outbox, inbox, retries, error queue, both CLI commands) carries the
> event between shipment and customs.

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
