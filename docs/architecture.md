# Architecture

## Styles in use

| Style / pattern                | How it shows up in the codebase                                                                                   |
| ------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| Service-Oriented Architecture  | One deployable service exposing an autonomous, contract-first API (`openapi.yaml`, `asyncapi.yaml` per module).      |
| Strategic DDD                  | Two bounded contexts — `shipment` and `customs_clearance` — integrated only by events; no shared tables or FKs.      |
| Tactical DDD                   | Aggregate roots, internal entities, value objects, domain events and repositories per aggregate.                    |
| Modular monolith               | `modules/<module>` are physically separated packages with a private PostgreSQL schema each.                         |
| Vertical Slice Architecture    | `features/<use_case>/` holds the controller, command DTO and handler of a single use case, side by side.            |
| Clean Architecture             | Dependencies point inwards: `features` → `domain`; `infrastructure` → `domain`. The domain imports nothing outward. |
| CQRS                           | Commands are Pydantic DTOs handled by a single command handler; queries get their own read-optimized slices.        |
| Event-Driven Architecture      | Integration events cross module boundaries through a transactional outbox and a de-duplicating inbox.               |
| Task-Based HTTP API            | Endpoints are named after business tasks (`POST /shipments/{id}/finalize-manifest`), never CRUD.                     |

## Dependency rules

```
modules/shipment/src/features ─────┐
                                   ├──► modules/shipment/src/domain  ◄── pure Python only
modules/shipment/src/infrastructure┘

modules/shipment  ──►  modules/shared
modules/customs_clearance  ──►  modules/shared

modules/shipment  ✗  modules/customs_clearance    (never a direct import)
modules/shared    ✗  any business module
```

* The **domain layer** never imports SQLAlchemy, FastAPI or Pydantic. Value
  objects are plain immutable Python objects implementing
  `__composite_values__` so SQLAlchemy can map them as composites.
* Persistence is attached with **imperative (classical) mapping**: tables live
  in `infrastructure/database/entities`, and `start_mappers()` binds the domain
  classes to them at start-up (called from `main.py`).
* Cross-context references are stored as **primitive identifiers** (for
  instance `ClearanceCase.shipmentId` is a plain string) to keep the contexts
  decoupled at the database level.

## Error handling

Every failure is translated into an [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457)
Problem Details document with the `application/problem+json` media type:

* `modules/shared/domain/errors.py` — framework-agnostic error hierarchy raised
  by the domain and application layers.
* `modules/shared/http/exceptions/` — the single place that maps those errors
  (plus validation and unhandled failures) to a problem document.

## Transactional consistency

A command handler and the integration events it produces are written in the
**same database transaction**: the request-scoped session
(`modules/shared/database/session.py`) commits once, covering both the
aggregate tables and the module `outbox` table. A background dispatcher then
publishes the outbox rows to RabbitMQ — that dispatcher is out of scope for the
current milestone.

## Deferred on purpose

* Message bus wiring (publisher, consumers, idempotency, retries) —
  `modules/shared/message_bus` is an empty placeholder; RabbitMQ is already
  provisioned in `docker-compose.yaml`.
* Business use cases of both modules.
* CI/CD and repository setup.
