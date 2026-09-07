"""Unit tests for the *assign complex route* use case."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from modules.shared.http.exceptions.problem_details import PROBLEM_CONTENT_TYPE
from modules.shipment.src.domain.enums import TrackingStatus
from modules.shipment.src.domain.exceptions import (
    InvalidShipmentIdError,
    InvalidShipmentRouteError,
    RouteNotModifiableError,
    ShipmentNotFoundError,
)
from modules.shipment.src.domain.shipment import Shipment
from modules.shipment.src.domain.value_objects import ShipmentId, WaybillNumber
from modules.shipment.src.features.assign_route import (
    AssignRouteCommand,
    AssignRouteHandler,
    get_assign_route_handler,
)
from modules.shipment.test.doubles import InMemoryShipmentRepository


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


@pytest.fixture
def shipment() -> Shipment:
    return make_shipment()


@pytest.fixture
def repository(shipment: Shipment) -> InMemoryShipmentRepository:
    return InMemoryShipmentRepository(shipment)


@pytest.fixture
def handler(repository: InMemoryShipmentRepository) -> AssignRouteHandler:
    return AssignRouteHandler(shipments=repository)


class TestHandler:
    async def test_replaces_the_itinerary(
        self,
        handler: AssignRouteHandler,
        shipment: Shipment,
    ) -> None:
        updated = await handler.handle(
            str(shipment.id),
            AssignRouteCommand(
                origin_port_code="ESVLC",
                destination_port_code="USNYC",
                transit_legs=["MAMIR", "PTLIS"],
            ),
        )

        assert updated is shipment
        assert updated.route.transit_legs == ("MAMIR", "PTLIS")
        assert str(updated.route) == "ESVLC > MAMIR > PTLIS > USNYC"

    async def test_accepts_a_direct_route_without_legs(
        self,
        handler: AssignRouteHandler,
        shipment: Shipment,
    ) -> None:
        updated = await handler.handle(
            str(shipment.id),
            AssignRouteCommand(
                origin_port_code="ESBCN",
                destination_port_code="USLAX",
            ),
        )

        assert updated.route.transit_legs == ()
        assert updated.route.origin_port_code == "ESBCN"

    async def test_leaves_the_status_untouched(
        self,
        handler: AssignRouteHandler,
        shipment: Shipment,
    ) -> None:
        updated = await handler.handle(
            str(shipment.id),
            AssignRouteCommand(
                origin_port_code="ESVLC",
                destination_port_code="USNYC",
                transit_legs=["MAMIR"],
            ),
        )

        assert updated.status is TrackingStatus.DRAFT

    async def test_persists_the_aggregate(
        self,
        handler: AssignRouteHandler,
        repository: InMemoryShipmentRepository,
        shipment: Shipment,
    ) -> None:
        await handler.handle(
            str(shipment.id),
            AssignRouteCommand(
                origin_port_code="ESVLC",
                destination_port_code="USNYC",
                transit_legs=["MAMIR"],
            ),
        )

        assert repository.persisted == [shipment]

    async def test_rejects_an_unknown_shipment(
        self,
        handler: AssignRouteHandler,
    ) -> None:
        with pytest.raises(ShipmentNotFoundError):
            await handler.handle(
                str(ShipmentId.generate()),
                AssignRouteCommand(
                    origin_port_code="ESVLC",
                    destination_port_code="USNYC",
                ),
            )

    async def test_rejects_a_malformed_identifier(
        self,
        handler: AssignRouteHandler,
    ) -> None:
        with pytest.raises(InvalidShipmentIdError):
            await handler.handle(
                "not-a-uuid",
                AssignRouteCommand(
                    origin_port_code="ESVLC",
                    destination_port_code="USNYC",
                ),
            )

    @pytest.mark.parametrize(
        "status",
        [
            TrackingStatus.AWAITING_CUSTOMS_RELEASE,
            TrackingStatus.IN_TRANSIT,
            TrackingStatus.DELIVERED,
        ],
    )
    async def test_refuses_to_reroute_a_locked_shipment(
        self,
        status: TrackingStatus,
    ) -> None:
        locked = make_shipment(status)
        handler = AssignRouteHandler(shipments=InMemoryShipmentRepository(locked))

        with pytest.raises(RouteNotModifiableError):
            await handler.handle(
                str(locked.id),
                AssignRouteCommand(
                    origin_port_code="ESVLC",
                    destination_port_code="USNYC",
                    transit_legs=["MAMIR"],
                ),
            )

    @pytest.mark.parametrize(
        "status",
        [
            TrackingStatus.DRAFT,
            TrackingStatus.READY_FOR_MANIFEST,
            TrackingStatus.EXCEPTION_HELD,
        ],
    )
    async def test_allows_rerouting_before_customs_takes_over(
        self,
        status: TrackingStatus,
    ) -> None:
        reroutable = make_shipment(status)
        handler = AssignRouteHandler(shipments=InMemoryShipmentRepository(reroutable))

        updated = await handler.handle(
            str(reroutable.id),
            AssignRouteCommand(
                origin_port_code="ESVLC",
                destination_port_code="USNYC",
                transit_legs=["MAMIR"],
            ),
        )

        assert updated.route.transit_legs == ("MAMIR",)

    @pytest.mark.parametrize(
        "transit_legs",
        [
            ["ESVLC"],
            ["USNYC"],
            ["MAMIR", "MAMIR"],
        ],
    )
    async def test_rejects_an_illogical_sequence(
        self,
        handler: AssignRouteHandler,
        shipment: Shipment,
        transit_legs: list[str],
    ) -> None:
        with pytest.raises(InvalidShipmentRouteError):
            await handler.handle(
                str(shipment.id),
                AssignRouteCommand(
                    origin_port_code="ESVLC",
                    destination_port_code="USNYC",
                    transit_legs=transit_legs,
                ),
            )


@pytest.fixture
def endpoint(app: FastAPI, handler: AssignRouteHandler) -> Iterator[None]:
    """Serve the endpoint with the in-memory handler, so no database is used."""
    app.dependency_overrides[get_assign_route_handler] = lambda: handler
    yield
    app.dependency_overrides.pop(get_assign_route_handler, None)


class TestEndpoint:
    async def test_answers_with_the_updated_route(
        self,
        endpoint: None,
        client: AsyncClient,
        shipment: Shipment,
    ) -> None:
        response = await client.put(
            f"/shipments/{shipment.id}/route",
            json={
                "origin_port_code": "ESVLC",
                "destination_port_code": "USNYC",
                "transit_legs": ["MAMIR", "PTLIS"],
            },
        )

        assert response.status_code == 200

        body = response.json()
        assert body["shipment_id"] == str(shipment.id)
        assert body["waybill_number"] == "MUST-0000001"
        assert body["status"] == TrackingStatus.DRAFT
        assert body["route"] == {
            "origin_port_code": "ESVLC",
            "destination_port_code": "USNYC",
            "transit_legs": ["MAMIR", "PTLIS"],
        }

    async def test_links_to_the_tasks_allowed_next(
        self,
        endpoint: None,
        client: AsyncClient,
        shipment: Shipment,
    ) -> None:
        response = await client.put(
            f"/shipments/{shipment.id}/route",
            json={
                "origin_port_code": "ESVLC",
                "destination_port_code": "USNYC",
                "transit_legs": ["MAMIR"],
            },
        )

        links = {link["rel"]: link for link in response.json()["_links"]}

        assert links["assign-route"]["method"] == "PUT"
        assert links["assign-route"]["href"] == f"/shipments/{shipment.id}/route"
        assert links["finalize-manifest"]["method"] == "POST"
        assert links["finalize-manifest"]["href"] == (
            f"/shipments/{shipment.id}/finalize-manifest"
        )

    async def test_reports_an_unknown_shipment_as_problem_details(
        self,
        endpoint: None,
        client: AsyncClient,
    ) -> None:
        response = await client.put(
            f"/shipments/{ShipmentId.generate()}/route",
            json={
                "origin_port_code": "ESVLC",
                "destination_port_code": "USNYC",
            },
        )

        assert response.status_code == 404
        assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
        assert response.json()["type"].endswith("/shipment-not-found")

    async def test_reports_a_locked_route_as_problem_details(
        self,
        app: FastAPI,
        client: AsyncClient,
    ) -> None:
        locked = make_shipment(TrackingStatus.IN_TRANSIT)
        handler = AssignRouteHandler(shipments=InMemoryShipmentRepository(locked))
        app.dependency_overrides[get_assign_route_handler] = lambda: handler

        try:
            response = await client.put(
                f"/shipments/{locked.id}/route",
                json={
                    "origin_port_code": "ESVLC",
                    "destination_port_code": "USNYC",
                    "transit_legs": ["MAMIR"],
                },
            )
        finally:
            app.dependency_overrides.pop(get_assign_route_handler, None)

        assert response.status_code == 409
        assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
        assert response.json()["type"].endswith("/route-not-modifiable")

    async def test_reports_an_illogical_sequence_as_problem_details(
        self,
        endpoint: None,
        client: AsyncClient,
        shipment: Shipment,
    ) -> None:
        response = await client.put(
            f"/shipments/{shipment.id}/route",
            json={
                "origin_port_code": "ESVLC",
                "destination_port_code": "USNYC",
                "transit_legs": ["ESVLC"],
            },
        )

        assert response.status_code == 422
        assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
        assert response.json()["type"].endswith("/invalid-shipment-route")

    async def test_reports_a_malformed_payload_as_problem_details(
        self,
        endpoint: None,
        client: AsyncClient,
        shipment: Shipment,
    ) -> None:
        response = await client.put(
            f"/shipments/{shipment.id}/route",
            json={"origin_port_code": "ES", "destination_port_code": "USNYC"},
        )

        assert response.status_code == 422
        assert response.json()["type"].endswith("/request-validation-failed")
