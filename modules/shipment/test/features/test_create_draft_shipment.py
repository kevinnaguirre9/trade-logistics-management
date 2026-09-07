"""Unit tests for the *create draft shipment* use case."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from modules.shared.http.exceptions.problem_details import PROBLEM_CONTENT_TYPE
from modules.shipment.src.domain.enums import TrackingStatus
from modules.shipment.src.domain.exceptions import InvalidShipmentRouteError
from modules.shipment.src.domain.value_objects import WaybillNumber
from modules.shipment.src.features.create_draft_shipment import (
    CreateDraftShipmentCommand,
    CreateDraftShipmentHandler,
    get_create_draft_shipment_handler,
)
from modules.shipment.test.doubles import (
    InMemoryShipmentRepository,
    StubWaybillNumberGenerator,
)


@pytest.fixture
def repository() -> InMemoryShipmentRepository:
    return InMemoryShipmentRepository()


@pytest.fixture
def handler(repository: InMemoryShipmentRepository) -> CreateDraftShipmentHandler:
    return CreateDraftShipmentHandler(
        shipments=repository,
        waybill_numbers=StubWaybillNumberGenerator(),
    )


class TestHandler:
    async def test_opens_the_shipment_as_a_draft(
        self,
        handler: CreateDraftShipmentHandler,
    ) -> None:
        shipment = await handler.handle(
            CreateDraftShipmentCommand(
                origin_port_code="ESVLC",
                destination_port_code="USNYC",
            )
        )

        assert shipment.status is TrackingStatus.DRAFT
        assert shipment.route.origin_port_code == "ESVLC"
        assert shipment.route.destination_port_code == "USNYC"

    async def test_assigns_a_structured_waybill_number(
        self,
        handler: CreateDraftShipmentHandler,
    ) -> None:
        shipment = await handler.handle(
            CreateDraftShipmentCommand(
                origin_port_code="ESVLC",
                destination_port_code="USNYC",
            )
        )

        assert shipment.waybill_number == WaybillNumber("MUST-0000001")

    async def test_persists_the_whole_aggregate(
        self,
        handler: CreateDraftShipmentHandler,
        repository: InMemoryShipmentRepository,
    ) -> None:
        shipment = await handler.handle(
            CreateDraftShipmentCommand(
                origin_port_code="ESVLC",
                destination_port_code="USNYC",
            )
        )

        assert repository.persisted == [shipment]
        assert await repository.find_by_id(shipment.id) is shipment

    async def test_issues_a_different_number_per_shipment(
        self,
        handler: CreateDraftShipmentHandler,
    ) -> None:
        command = CreateDraftShipmentCommand(
            origin_port_code="ESVLC",
            destination_port_code="USNYC",
        )

        first = await handler.handle(command)
        second = await handler.handle(command)

        assert first.waybill_number != second.waybill_number
        assert first.id != second.id

    async def test_refuses_a_route_that_ends_where_it_starts(
        self,
        handler: CreateDraftShipmentHandler,
        repository: InMemoryShipmentRepository,
    ) -> None:
        with pytest.raises(InvalidShipmentRouteError):
            await handler.handle(
                CreateDraftShipmentCommand(
                    origin_port_code="ESVLC",
                    destination_port_code="ESVLC",
                )
            )

        assert repository.persisted == []


@pytest.fixture
def endpoint(
    app: FastAPI,
    handler: CreateDraftShipmentHandler,
) -> Iterator[None]:
    """Serve ``POST /shipments`` with in-memory collaborators (no database)."""
    app.dependency_overrides[get_create_draft_shipment_handler] = lambda: handler
    yield
    app.dependency_overrides.clear()


class TestEndpoint:
    async def test_answers_created_with_the_new_resource(
        self,
        endpoint: None,
        client: AsyncClient,
    ) -> None:
        response = await client.post(
            "/shipments",
            json={"origin_port_code": "ESVLC", "destination_port_code": "USNYC"},
        )

        assert response.status_code == 201

        body = response.json()
        assert body["waybill_number"] == "MUST-0000001"
        assert body["status"] == TrackingStatus.DRAFT
        assert body["shipment_id"]

    async def test_links_to_the_tasks_allowed_next(
        self,
        endpoint: None,
        client: AsyncClient,
    ) -> None:
        response = await client.post(
            "/shipments",
            json={"origin_port_code": "ESVLC", "destination_port_code": "USNYC"},
        )

        body = response.json()
        links = {link["rel"]: link for link in body["_links"]}

        assert links["assign-route"]["method"] == "PUT"
        assert links["assign-route"]["href"] == (
            f"/shipments/{body['shipment_id']}/route"
        )
        assert links["finalize-manifest"]["method"] == "POST"
        assert links["finalize-manifest"]["href"] == (
            f"/shipments/{body['shipment_id']}/finalize-manifest"
        )

    async def test_reports_a_broken_invariant_as_problem_details(
        self,
        endpoint: None,
        client: AsyncClient,
    ) -> None:
        response = await client.post(
            "/shipments",
            json={"origin_port_code": "ESVLC", "destination_port_code": "ESVLC"},
        )

        assert response.status_code == 422
        assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)

        problem = response.json()
        assert problem["type"].endswith("/invalid-shipment-route")
        assert problem["instance"] == "/shipments"

    async def test_reports_a_malformed_payload_as_problem_details(
        self,
        endpoint: None,
        client: AsyncClient,
    ) -> None:
        response = await client.post(
            "/shipments",
            json={"origin_port_code": "ES", "destination_port_code": "USNYC"},
        )

        assert response.status_code == 422
        assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)

        problem = response.json()
        assert problem["type"].endswith("/request-validation-failed")
        assert problem["errors"]
