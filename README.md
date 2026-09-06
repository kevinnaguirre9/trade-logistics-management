# Trade Logistics Management

International Freight & Customs Clearance service, built as a **modular
monolith** with two bounded contexts:

| Module              | Schema     | Responsibility                                        |
| ------------------- | ---------- | ----------------------------------------------------- |
| `shipment`          | `shipment` | Cargo lifecycle, routing and transport readiness       |
| `customs_clearance` | `customs`  | Regulatory compliance state machine (duty, documents)  |

Both modules share only the `modules/shared` kernel and talk to each other
exclusively through integration events (outbox/inbox over RabbitMQ).

> **Status:** project scaffolding only. No use case of either module is
> implemented yet, and the message bus is intentionally not wired.

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

## Quality gates

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
