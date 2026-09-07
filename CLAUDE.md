# Project contect: International Freight & Customs Clearance

## 1. Fully Detailed Bounded Context: Shipment Management (`shipment` schema)

This module handles the physical lifecycle, route constraints, and transport readiness of the cargo.

### Detailed Aggregates & Value Objects

#### **Shipment Aggregate (Root)**

* **Properties:**
* `id: ShipmentId` (Strongly typed UUID value object)
* `waybillNumber: WaybillNumber`
* `manifest: CargoManifest`
* `route: ShipmentRoute`
* `status: TrackingStatus` (Enum: `Draft`, `ReadyForManifest`, `AwaitingCustomsRelease`, `InTransit`, `Delivered`, `ExceptionHeld`)


* **Value Objects (No ORM Decorators, Pure Python):**
* `ShipmentId`: Contains standard UUID validation.
* `WaybillNumber`: Enforces regex for carrier prefix and serial format (e.g., `^MUST-[0-9]{7}$`). Implements `equals()` method.
* `CargoManifest`: Read-only properties for `totalWeightKg: number`, `totalVolumeCbm: number`, and `commodityCode: string`. Invariant check: cannot have negative numbers.
* `ShipmentRoute`: Read-only properties for `originPortCode: string`, `destinationPortCode: string`, and `transitLegs: string[]`. Invariant check: origin cannot equal destination.



---

### Exhaustive List of Use Cases & Feature Slices

#### **Use Case 1: Create Draft Shipment**

* **Type:** HTTP Controller $\rightarrow$ Command $\rightarrow$ Command Handler.
* **Task-Based Endpoint:** `POST /shipments`
* **Payload:** `{ origin_port_code: string, destination_port_code: string }`
* **Aggregate Method Invoked:** `const shipment = Shipment.create(id, waybillGenerator.next(), origin, destination)`
* **Domain Behavior & Invariants:** Initializes the aggregate status to `Draft`. Generates a unique, structured tracking number.
* **Database Operation:** `repository.persist(shipment)` (Insert into `shipment.shipments`).
* **Messages Generated:** None (This is a local setup step).
* **HATEOAS Links Returned:** * `assign-route` $\rightarrow$ `PUT /shipments/{id}/route`
* `finalize-manifest` $\rightarrow$ `POST /shipments/{id}/finalize-manifest`



#### **Use Case 2: Assign Complex Route**

* **Type:** HTTP Controller $\rightarrow$ Command $\rightarrow$ Command Handler.
* **Task-Based Endpoint:** `PUT /shipments/{id}/route`
* **Payload:** `{ origin_port_code: string, destination_port_code: string, transit_legs: string[] }`
* **Aggregate Method Invoked:** `shipment.assignRoute(newRoute)`
* **Domain Behavior & Invariants:** * Cannot modify the route if the status is `AwaitingCustomsRelease`, `InTransit`, or `Delivered`.
* Validates that the array of `transitLegs` forms a logical sequence starting at the origin and ending at the destination.


* **Database Operation:** `repository.persist(shipment)`
* **Messages Generated:** None.

#### **Use Case 3: Finalize Cargo Manifest**

* **Type:** HTTP Controller $\rightarrow$ Command $\rightarrow$ Command Handler.
* **Task-Based Endpoint:** `POST /shipments/{id}/finalize-manifest`
* **Payload:** `{ total_weight_kg: number, total_volume_cbm: number, commodity_code: string }`
* **Aggregate Method Invoked:** `shipment.finalizeManifest(newManifest)`
* **Domain Behavior & Invariants:**
* Can only be finalized if status is `Draft`.
* Enforces that `totalWeightKg` must be strictly greater than $0$.
* Mutates state `status = TrackingStatus.ReadyForManifest`.


* **Database Operation:** Saves updated shipment **AND** inserts `ShipmentManifestFinalized` integration event into `shipment.outbox` within the same database transaction.
* **Messages Generated (Outbox):** `ShipmentManifestFinalized` event containing `shipment_id`, `waybill_number`, and `commodity_code`.

#### **Use Case 4: Hold for Customs Inspection**

* **Type:** Message Handler (Inbox) $\rightarrow$ Command $\rightarrow$ Command Handler.
* **Trigger:** Triggered automatically by a system component or a background process once the manifest is flagged across the broker. *For your implementation, you can choose to auto-invoke this immediately after Use Case 3 is processed by the application layer, or let it respond to its own event stream via Inbox.*
* **Aggregate Method Invoked:** `shipment.holdForCustoms()`
* **Domain Behavior & Invariants:** * Changes status from `ReadyForManifest` to `AwaitingCustomsRelease`.
* Locks the aggregate from any physical operations.


* **Database Operation:** Updates shipment state in `shipment.shipments`.
* **Messages Generated:** None.

#### **Use Case 5: Release for Transit**

* **Type:** Message Handler (Inbox) $\rightarrow$ Command $\rightarrow$ Command Handler.
* **Trigger:** Message Handler consumes `CustomsClearanceApproved` from RabbitMQ $\rightarrow$ stores in `shipment.inbox` $\rightarrow$ handles command.
* **Payload from Event:** `{ shipment_id: string, clearance_token: string }`
* **Aggregate Method Invoked:** `shipment.releaseForTransit(clearanceToken)`
* **Domain Behavior & Invariants:**
* Can *only* transition to `InTransit` if current status is exactly `AwaitingCustomsRelease`.
* Validates that the cryptographic `clearanceToken` is structurally valid (not empty/expired).
* Changes state `status = TrackingStatus.InTransit`.


* **Database Operation:** Updates shipment state, marks inbox message as processed.
* **Messages Generated:** None.

#### **Use Case 6: Flag Operational Exception**

* **Type:** HTTP Controller $\rightarrow$ Command $\rightarrow$ Command Handler (Invoked by a logistics operator if cargo is physically damaged or delayed at port).
* **Task-Based Endpoint:** `POST /shipments/{id}/flag-exception`
* **Payload:** `{ reason: string }`
* **Aggregate Method Invoked:** `shipment.flagException(reason)`
* **Domain Behavior & Invariants:**
* Cannot flag an exception if the shipment is already `Delivered`.
* Saves the string `reason` inside a non-nullable field.
* Changes state `status = TrackingStatus.ExceptionHeld`.


* **Database Operation:** Updates shipment state.
* **Messages Generated (Outbox):** `ShipmentDelayedExceptionRaised` (Optional integration event to alert notifications module).

---

## 2. Fully Detailed Bounded Context: Customs Clearance (`customs` schema)

This module operates as a dedicated state machine managing regulatory compliance.

### Detailed Aggregates & Value Objects

#### **ClearanceCase Aggregate (Root)**

* **Properties:**
* `id: CaseId` (UUID)
* `shipmentId: string` (Stored strictly as a primitive string identifier to preserve bounded context boundaries; no object or foreign-key level coupling to the shipment table).
* `declarationValue: Money`
* `documents: DocumentRegistryItem[]` (Internal Entity collection)
* `status: AssessmentStatus` (Enum: `Opened`, `DocumentVerification`, `RiskAssessment`, `DutyPaymentPending`, `Released`, `Rejected`)
* `dutyFee: Money`


* **Value Objects & Entities:**
* `Money`: `amount: number`, `currency: string`. Handles rounding rules and prevents cross-currency operations without an explicit converter.
* `DocumentRegistryItem` (Internal Entity): `documentId: UUID`, `type: string`, `s3Url: string`, `isVerified: boolean`, `verifiedByInspectorId: string | null`.



---

### Exhaustive List of Use Cases & Feature Slices

#### **Use Case 1: Open Clearance Case**

* **Type:** Message Handler (Inbox) $\rightarrow$ Command $\rightarrow$ Command Handler.
* **Trigger:** Consumes `ShipmentManifestFinalized` from RabbitMQ $\rightarrow$ writes to `customs.inbox`.
* **Payload from Event:** `{ shipment_id: string, commodity_code: string }`
* **Aggregate Method Invoked:** `const clearanceCase = ClearanceCase.openForShipment(id, shipmentId)`
* **Domain Behavior & Invariants:** Creates the tracking case with an initial status of `Opened`.
* **Database Operation:** Inserts record into `customs.clearance_cases`. Marks inbox message as completed.
* **Messages Generated:** None.

#### **Use Case 2: Attach Legal Document Reference**

* **Type:** HTTP Controller $\rightarrow$ Command $\rightarrow$ Command Handler.
* **Task-Based Endpoint:** `POST /customs/cases/{caseId}/documents`
* **Payload:** `{ document_type: 'COMMERCIAL_INVOICE' | 'BILL_OF_LADING', s3_url: string }`
* **Aggregate Method Invoked:** `clearanceCase.attachDocument(documentType, s3Url)`
* **Domain Behavior & Invariants:**
* Cannot attach documents if the case status is already `Released` or `Rejected`.
* Validates that the `s3Url` points to the expected bucket prefix format.
* If the case was in `Opened` state, transitions to `DocumentVerification` as soon as the first document is attached.


* **Database Operation:** Appends to the internal document collection table/schema (`customs.clearance_case_documents`).

#### **Use Case 3: Verify Document**

* **Type:** HTTP Controller $\rightarrow$ Command $\rightarrow$ Command Handler (Executed by a Customs Inspector).
* **Task-Based Endpoint:** `POST /customs/cases/{caseId}/documents/{docId}/verify`
* **Payload:** `{ inspector_id: string }`
* **Aggregate Method Invoked:** `clearanceCase.verifyDocument(docId, inspectorId)`
* **Domain Behavior & Invariants:**
* Locates the sub-entity item matching `docId`. Flips `isVerified = true` and logs the `inspectorId`.
* **Internal Invariant Check:** If both a `COMMERCIAL_INVOICE` and a `BILL_OF_LADING` are marked as `isVerified = true`, the aggregate automatically mutates its root status to `RiskAssessment`.


* **Database Operation:** Updates document sub-entity status and updates the aggregate root status to `RiskAssessment`.
* **Messages Generated:** None immediately out of the domain, but the application handler checks if the state changed to `RiskAssessment` to trigger the next background job slice.

#### **Use Case 4: Execute Autonomous Risk Assessment**

* **Type:** Internal Message Handler / Background Job Command (Dispatched instantly when Use Case 3 transitions the aggregate state to `RiskAssessment`).
* **Aggregate Method Invoked:** `clearanceCase.evaluateRisk(calculatedRiskScore)`
* **Domain Behavior & Invariants:**
* Can only be evaluated if current status is exactly `RiskAssessment`.
* If `calculatedRiskScore` is below a business threshold ($70/100$), it computes the `dutyFee` (e.g., a flat $10\%$ of an assumed declaration value for simplicity or passed via configuration) and sets status to `DutyPaymentPending`.
* If score is high, sets status to `Rejected`.


* **Database Operation:** Updates aggregate status and saves calculated `dutyFee` column values.
* **Messages Generated (Outbox):** If the status becomes `DutyPaymentPending`, it writes a `CustomsDutyAssessed` event to `customs.outbox`. If `Rejected`, writes `CustomsClearanceRejected`.

#### **Use Case 5: Process Secure Customs Release (Duty Payment)**

* **Type:** HTTP Controller $\rightarrow$ Command $\rightarrow$ Command Handler.
* **Task-Based Endpoint:** `POST /customs/cases/{caseId}/pay-duty`
* **Payload:** `{ reference_receipt_id: string, payment_amount: number, currency: string }`
* **Aggregate Method Invoked:** `clearanceCase.recordDutyPayment(referenceReceiptId, Money.create(paymentAmount, currency))`
* **Domain Behavior & Invariants:**
* Can only pay if state is `DutyPaymentPending`.
* **Strict Invariant:** The payment `Money` value object must perfectly match or exceed the calculated `dutyFee` value object.
* Mutates status to `Released`.


* **Database Operation:** Updates aggregate root state to `Released`. Inserts integration event to `customs.outbox`.
* **Messages Generated (Outbox):** Publishes `CustomsClearanceApproved` containing the `shipment_id` and a generated security clearance string token. This is the event consumed by **Use Case 5** of the Shipment Module.

---


# Tech Stack
* Programming Language: Python
* Framework: FastAPI
* Database: PostgreSQL LTS with Schemas per module
* ORM: SQL Alchemy
    * ORM mapping Style: Imperative Mapping
    * __composite_values__  for Value Objects
* Alembic: creation, management, and invocation of change management scripts for a relational database
    * Alembic use environment variables
* Message Queue: RabbitMQ
* Global error handling with Problem Details RFC
* Pytest for Testing
* Pydantic Base model for DTOs (e.g. command DTOs of CQRS)
* HTTP contract naming: request and response bodies use snake_case, identical to the Python field names (no camelCase aliasing)
* Toml as package manager
* Dockerfile with best practices (stages and small image size)
* Docker-compose with app, postgresql database LTS, pgadmin and rabbitmq LTS services
* .env.example with all ports and port forwards and database

---

# Architectural Styles and patterns to use
- Service-Oriented Architecture
- Strategic & Tactical Domain-Driven Design
- Modular monolith: modules are shipment and customs_clearance 
- Vertical Slice Architecture
- Clean architecture
- CQRS
- Event-Drive Architecture
- Task Based HTTP API

## Message Bus

The modules or services from the trade logistic management communicate via Event-Driven architecture.
They publish and consume messages (either commands or events) from RabbitMQ.

### Requirements

1. Implement a shared module with the following patterns and requirments
- Transactional Outbox pattern
- Inbox pattern
- Idempotency for deduplicating messages
- Inmediate retries and delayed retries
- Error queue (aka dead letter queue)
- CLI commands "dispatch-messages" and "handle-messages"
- CLI handle-message command must allow dynamic handling connections. In other words, we must be able to tell the configuration
  (exchange, queue, binding keys, error queue, retries, etc) we want to use.
- 

### Packages to use
- aio-pika
- FastAPI typer (optional if you find no actual benefits from it, let me know what you think first)

### Constraints
- Each module must have the outbox and inbox tables in their database schema
- Events or Commands that goes to RabbitMQ are just python classes
- The events or commands name reflect meaningful domain behavior, not CRUD.
- Handlers must be transaction, one failing handler doesn't roll back a sibling's completed work.


---

# Project Structure:
  /docs
  /modules
    /shipment
        /src
            /domain #agregate root, events, entities, value objects, etc
                /enums
                /events #business domain events classes (e.g. ShipmentManifestFinalized)
                /exceptions
                /value_objects
                /repositories #repository interface (persist whole aggregate method and find method)
            /features
                /create_draft_shipment
                    create_draft_shipment_controller.py #http controller
                    create_draft_shipment_command.py
                    create_draft_shipment_handler.py
                /assign_route
                    ...
            /infrastructure
                /database
                    /entities #
                    /migrations
                    /seeds
                /repositories #posgresql repository implementation (persist and find methods)
        /test #pytest unit tests
            /dommain #unit tests for domain models behavior (per aggregate)
            /features #unit tests for use cases in the features folders
        /asyncapi.yaml
        /openapi.yaml
    /shared
        /database #here goes SQL Alchemy session connection and configuration
        /http
            /exceptions //here goees problem details mapping rfc
        /message-bus //idempotency, retries, etc
  .env.example
  Dockerfile
  docker-compose.yaml
  ...

---

# Requirement
1. Create the sample project structure in the current directory. Include the creation of the shared module.
   - 
   - PEP 8 – Style Guide for Python Code
   - Do not build any feature of shipment and customs_clearance modules yet.
   - Ignore the message bus for now, we will focus on it later.
   - Ignore CI/CD and git repository, we will focus on it later.
 