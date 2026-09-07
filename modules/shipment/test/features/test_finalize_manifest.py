"""Unit tests for the *finalize cargo manifest* use case."""

from collections.abc import Iterator
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from modules.shared.http.exceptions.problem_details import PROBLEM_CONTENT_TYPE
from modules.shared.message_bus import IntegrationMessage
from modules.shipment.src.domain.enums import TrackingStatus
from modules.shipment.src.domain.events import ShipmentManifestFinalized
from modules.shipment.src.domain.exceptions import (
    InvalidCargoManifestError,
    ManifestNotFinalizableError,
    ShipmentNotFoundError,
)
from modules.shipment.src.domain.shipment import Shipment
from modules.shipment.src.domain.value_objects import ShipmentId, WaybillNumber
from modules.shipment.src.features.finalize_manifest import (
    FinalizeManifestCommand,
    FinalizeManifestHandler,
    get_finalize_manifest_handler,
)
from modules.shipment.test.doubles import InMemoryShipmentRepository


class InMemoryOutbox:
    """Test double standing in for the module outbox."""

    def __init__(self) -> None:
        self.scheduled: list[IntegrationMessage] = []

    async def schedule(
        self,
        message: IntegrationMessage,
        headers: dict[str, Any] | None = None,
        message_id: UUID | None = None,
    ) -> None:
        self.scheduled.append(message)


def make_shipment(status: TrackingStatus = TrackingStatus.DRAFT) -> Shipment:
    """Return a stored shipment in the requested lifecycle state."""
    shipment = Shipment.create(
        shipment_id=ShipmentId.generate(),
        waybill_number=WaybillNumber.from_serial(1),
        origin_port_code="ESVLC",
        destination_port_code="USNYC",
    )
    shipment.status = status
    return shipment


def a_command(
    total_weight_kg: float = 12_500.5,
    total_volume_cbm: float = 68.25,
    commodity_code: str = "8471",
) -> FinalizeManifestCommand:
    return FinalizeManifestCommand(
        total_weight_kg=total_weight_kg,
        total_volume_cbm=total_volume_cbm,
        commodity_code=commodity_code,
    )


@pytest.fixture
def shipment() -> Shipment:
    return make_shipment()


@pytest.fixture
def repository(shipment: Shipment) -> InMemoryShipmentRepository:
    return InMemoryShipmentRepository(shipment)


@pytest.fixture
def outbox() -> InMemoryOutbox:
    return InMemoryOutbox()


@pytest.fixture
def handler(
    repository: InMemoryShipmentRepository, outbox: InMemoryOutbox
) -> FinalizeManifestHandler:
    return FinalizeManifestHandler(shipments=repository, outbox=outbox)


class TestHandler:
    async def test_declares_the_cargo(
        self, handler: FinalizeManifestHandler, shipment: Shipment
    ) -> None:
        updated = await handler.handle(str(shipment.id), a_command())

        assert updated.manifest is not None
        assert updated.manifest.total_weight_kg == 12_500.5
        assert updated.manifest.total_volume_cbm == 68.25
        assert updated.manifest.commodity_code == "8471"

    async def test_moves_the_shipment_to_ready_for_manifest(
        self, handler: FinalizeManifestHandler, shipment: Shipment
    ) -> None:
        updated = await handler.handle(str(shipment.id), a_command())

        assert updated.status is TrackingStatus.READY_FOR_MANIFEST

    async def test_queues_the_integration_event(
        self,
        handler: FinalizeManifestHandler,
        shipment: Shipment,
        outbox: InMemoryOutbox,
    ) -> None:
        await handler.handle(str(shipment.id), a_command())

        assert len(outbox.scheduled) == 1
        event = outbox.scheduled[0]
        assert isinstance(event, ShipmentManifestFinalized)
        assert event.shipment_id == str(shipment.id)
        assert event.waybill_number == "MUST-0000001"
        assert event.commodity_code == "8471"

    async def test_persists_the_aggregate(
        self,
        handler: FinalizeManifestHandler,
        repository: InMemoryShipmentRepository,
        shipment: Shipment,
    ) -> None:
        await handler.handle(str(shipment.id), a_command())

        assert repository.persisted == [shipment]

    async def test_rejects_an_unknown_shipment(
        self, handler: FinalizeManifestHandler
    ) -> None:
        with pytest.raises(ShipmentNotFoundError):
            await handler.handle(str(ShipmentId.generate()), a_command())

    @pytest.mark.parametrize(
        "status",
        [
            TrackingStatus.READY_FOR_MANIFEST,
            TrackingStatus.AWAITING_CUSTOMS_RELEASE,
            TrackingStatus.IN_TRANSIT,
            TrackingStatus.DELIVERED,
            TrackingStatus.EXCEPTION_HELD,
        ],
    )
    async def test_refuses_anything_that_is_not_a_draft(
        self, status: TrackingStatus, outbox: InMemoryOutbox
    ) -> None:
        shipment = make_shipment(status)
        handler = FinalizeManifestHandler(
            shipments=InMemoryShipmentRepository(shipment), outbox=outbox
        )

        with pytest.raises(ManifestNotFinalizableError):
            await handler.handle(str(shipment.id), a_command())

        assert outbox.scheduled == []

    @pytest.mark.parametrize("weight", [0, 0.0])
    async def test_refuses_a_shipment_with_no_weight(
        self,
        handler: FinalizeManifestHandler,
        shipment: Shipment,
        outbox: InMemoryOutbox,
        weight: float,
    ) -> None:
        with pytest.raises(InvalidCargoManifestError):
            await handler.handle(str(shipment.id), a_command(total_weight_kg=weight))

        assert shipment.status is TrackingStatus.DRAFT
        assert outbox.scheduled == []

    async def test_refuses_a_negative_weight(
        self, handler: FinalizeManifestHandler, shipment: Shipment
    ) -> None:
        with pytest.raises(InvalidCargoManifestError):
            await handler.handle(str(shipment.id), a_command(total_weight_kg=-1))

    async def test_accepts_a_zero_volume(
        self, handler: FinalizeManifestHandler, shipment: Shipment
    ) -> None:
        updated = await handler.handle(str(shipment.id), a_command(total_volume_cbm=0))

        assert updated.manifest is not None
        assert updated.manifest.total_volume_cbm == 0.0


@pytest.fixture
def endpoint(app: FastAPI, handler: FinalizeManifestHandler) -> Iterator[None]:
    """Serve the endpoint with the in-memory handler, so no database is used."""
    app.dependency_overrides[get_finalize_manifest_handler] = lambda: handler
    yield
    app.dependency_overrides.pop(get_finalize_manifest_handler, None)


class TestEndpoint:
    async def test_answers_with_the_declared_manifest(
        self, endpoint: None, client: AsyncClient, shipment: Shipment
    ) -> None:
        response = await client.post(
            f"/shipments/{shipment.id}/finalize-manifest",
            json={
                "total_weight_kg": 12500.5,
                "total_volume_cbm": 68.25,
                "commodity_code": "8471",
            },
        )

        assert response.status_code == 200

        body = response.json()
        assert body["shipment_id"] == str(shipment.id)
        assert body["waybill_number"] == "MUST-0000001"
        assert body["status"] == TrackingStatus.READY_FOR_MANIFEST
        assert body["manifest"] == {
            "total_weight_kg": 12500.5,
            "total_volume_cbm": 68.25,
            "commodity_code": "8471",
        }

    async def test_links_to_the_tasks_allowed_next(
        self, endpoint: None, client: AsyncClient, shipment: Shipment
    ) -> None:
        response = await client.post(
            f"/shipments/{shipment.id}/finalize-manifest",
            json={
                "total_weight_kg": 1.0,
                "total_volume_cbm": 1.0,
                "commodity_code": "8471",
            },
        )

        links = {link["rel"]: link for link in response.json()["_links"]}

        assert set(links) == {"assign-route", "flag-exception"}
        assert links["assign-route"]["method"] == "PUT"
        assert links["flag-exception"]["href"] == (
            f"/shipments/{shipment.id}/flag-exception"
        )

    async def test_reports_an_unknown_shipment_as_problem_details(
        self, endpoint: None, client: AsyncClient
    ) -> None:
        response = await client.post(
            f"/shipments/{ShipmentId.generate()}/finalize-manifest",
            json={
                "total_weight_kg": 1.0,
                "total_volume_cbm": 1.0,
                "commodity_code": "8471",
            },
        )

        assert response.status_code == 404
        assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
        assert response.json()["type"].endswith("/shipment-not-found")

    async def test_reports_a_shipment_past_draft_as_problem_details(
        self, app: FastAPI, client: AsyncClient, outbox: InMemoryOutbox
    ) -> None:
        shipment = make_shipment(TrackingStatus.IN_TRANSIT)
        handler = FinalizeManifestHandler(
            shipments=InMemoryShipmentRepository(shipment), outbox=outbox
        )
        app.dependency_overrides[get_finalize_manifest_handler] = lambda: handler

        try:
            response = await client.post(
                f"/shipments/{shipment.id}/finalize-manifest",
                json={
                    "total_weight_kg": 1.0,
                    "total_volume_cbm": 1.0,
                    "commodity_code": "8471",
                },
            )
        finally:
            app.dependency_overrides.pop(get_finalize_manifest_handler, None)

        assert response.status_code == 409
        assert response.json()["type"].endswith("/manifest-not-finalizable")

    async def test_reports_a_weightless_manifest_as_problem_details(
        self, endpoint: None, client: AsyncClient, shipment: Shipment
    ) -> None:
        response = await client.post(
            f"/shipments/{shipment.id}/finalize-manifest",
            json={
                "total_weight_kg": 0,
                "total_volume_cbm": 1.0,
                "commodity_code": "8471",
            },
        )

        assert response.status_code == 422
        assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
        assert response.json()["type"].endswith("/invalid-cargo-manifest")

    async def test_reports_a_malformed_payload_as_problem_details(
        self, endpoint: None, client: AsyncClient, shipment: Shipment
    ) -> None:
        response = await client.post(
            f"/shipments/{shipment.id}/finalize-manifest",
            json={"total_weight_kg": 1.0, "commodity_code": "8471"},
        )

        assert response.status_code == 422
        assert response.json()["type"].endswith("/request-validation-failed")
