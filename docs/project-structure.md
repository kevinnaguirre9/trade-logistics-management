# Project structure

```
.
├── alembic/                       # Alembic environment (revisions live in the modules)
│   ├── env.py                     # async engine, shared metadata, one schema per module
│   ├── script.py.mako
│   └── versions/                  # unused: every revision belongs to a module
├── docker/postgres/init/          # SQL executed once on an empty database (module schemas)
├── docs/
├── modules/
│   ├── shared/                    # shared kernel — never imports a business module
│   │   ├── config/                # environment-driven settings
│   │   ├── database/              # metadata, imperative-mapping registry, async session
│   │   ├── domain/                # framework-agnostic error hierarchy
│   │   ├── http/                  # RFC 9457 problem details + hypermedia helpers
│   │   │   └── exceptions/
│   │   └── message_bus/           # placeholder (idempotency, retries) — deferred
│   ├── shipment/
│   │   ├── asyncapi.yaml          # integration message contracts
│   │   ├── openapi.yaml           # task-based HTTP contract
│   │   ├── src/
│   │   │   ├── api.py             # module router: mounts every feature controller
│   │   │   ├── domain/            # aggregate roots, entities, value objects
│   │   │   │   ├── enums/
│   │   │   │   ├── events/
│   │   │   │   ├── exceptions/
│   │   │   │   ├── repositories/  # interfaces: persist(aggregate) / find_by_id(id)
│   │   │   │   └── value_objects/
│   │   │   ├── features/          # one folder per use case (vertical slice)
│   │   │   │   ├── create_draft_shipment/
│   │   │   │   ├── assign_route/
│   │   │   │   ├── finalize_manifest/
│   │   │   │   ├── hold_for_customs/
│   │   │   │   ├── release_for_transit/
│   │   │   │   └── flag_exception/
│   │   │   └── infrastructure/
│   │   │       ├── database/
│   │   │       │   ├── entities/      # Table definitions + start_mappers()
│   │   │       │   ├── migrations/    # Alembic revisions of this module
│   │   │       │   └── seeds/
│   │   │       └── repositories/      # PostgreSQL repository implementations
│   │   └── test/
│   │       ├── domain/            # aggregate behaviour unit tests
│   │       └── features/          # use case unit tests
│   └── customs_clearance/         # same layout; features:
│       └── src/features/{open_clearance_case, attach_document, verify_document,
│                         execute_risk_assessment, record_duty_payment}
├── tests/                         # composition-root (application-wide) tests
├── conftest.py                    # shared pytest fixtures (app, ASGI client)
├── main.py                        # composition root: settings, mappers, routers, errors
├── alembic.ini
├── docker-compose.yaml            # app + postgres + pgadmin + rabbitmq
├── Dockerfile                     # multi-stage, non-root, slim runtime
├── pyproject.toml                 # dependencies, Ruff (PEP 8) and pytest configuration
└── .env.example
```

## Naming conventions inside a vertical slice

An HTTP-triggered slice:

```
features/create_draft_shipment/
├── create_draft_shipment_controller.py   # FastAPI router: HTTP + HATEOAS links
├── create_draft_shipment_command.py      # Pydantic command DTO
└── create_draft_shipment_handler.py      # orchestrates aggregate + repository
```

A message-triggered slice replaces the controller with a message handler. It
plays the same role — turning a delivery into a command — so the rest of the
slice is identical:

```
features/open_clearance_case/
├── open_clearance_case_message_handler.py   # MessageHandler: inbox + command
├── open_clearance_case_command.py           # Pydantic command DTO
└── open_clearance_case_handler.py           # orchestrates aggregate + repository
```

A module's message handlers are collected in `src/message_bus.py`, the
messaging counterpart of `src/api.py`, and mounted by `worker.py`.
## Deviations from the original outline

* `message-bus` and `http/exceptions` are written as `message_bus` — Python
  package names cannot contain hyphens (PEP 8).
* `modules/shared/domain/` was added so the shared error hierarchy stays free of
  any framework import; `modules/shared/http/exceptions/` only maps those errors
  to Problem Details.
* `tests/` at the root holds composition-root smoke tests; per-module unit tests
  stay in `modules/<module>/test/` as specified.
