# Trade Logistics Management

International Freight & Customs Clearance service, built as a **modular
monolith** with two bounded contexts:

| Module              | Schema     | Responsibility                                        |
| ------------------- | ---------- | ----------------------------------------------------- |
| `shipment`          | `shipment` | Cargo lifecycle, routing and transport readiness       |
| `customs_clearance` | `customs`  | Regulatory compliance state machine (duty, documents)  |

Both modules share only the `modules/shared` kernel and talk to each other
exclusively through integration events (outbox/inbox over RabbitMQ).

> **Status:** the *create draft shipment* slice (`POST /shipments`) is
> implemented. The remaining use cases and the message bus are not wired yet.

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
