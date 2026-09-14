"""Unit tests for the *open clearance case* use case."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from modules.customs_clearance.src.domain.enums import AssessmentStatus
from modules.customs_clearance.src.features.open_clearance_case import (
    OpenClearanceCaseCommand,
    OpenClearanceCaseHandler,
    OpenClearanceCaseMessageHandler,
)
from modules.customs_clearance.test.doubles import InMemoryClearanceCaseRepository
from modules.shared.message_bus import MessageEnvelope


@pytest.fixture
def repository() -> InMemoryClearanceCaseRepository:
    return InMemoryClearanceCaseRepository()


@pytest.fixture
def handler(
    repository: InMemoryClearanceCaseRepository,
) -> OpenClearanceCaseHandler:
    return OpenClearanceCaseHandler(clearance_cases=repository)


def a_command(
    shipment_id: str = "3468ff71-574c-48f1-8af6-fd889d66eeef",
    commodity_code: str = "8471",
) -> OpenClearanceCaseCommand:
    return OpenClearanceCaseCommand(
        shipment_id=shipment_id,
        commodity_code=commodity_code,
    )


class TestCommand:
    def test_ignores_fields_the_publisher_added(self) -> None:
        command = OpenClearanceCaseCommand(
            shipment_id="s-1",
            commodity_code="8471",
            waybill_number="MUST-0000001",
        )

        assert command.shipment_id == "s-1"

    @pytest.mark.parametrize(
        "body",
        [
            {"commodity_code": "8471"},
            {"shipment_id": "", "commodity_code": "8471"},
            {"shipment_id": "s-1"},
        ],
    )
    def test_rejects_a_malformed_message_body(self, body: dict[str, str]) -> None:
        with pytest.raises(ValidationError):
            OpenClearanceCaseCommand(**body)


class TestHandler:
    async def test_opens_the_case_for_the_shipment(
        self, handler: OpenClearanceCaseHandler
    ) -> None:
        clearance_case = await handler.handle(a_command())

        assert clearance_case.shipment_id == "3468ff71-574c-48f1-8af6-fd889d66eeef"
        assert clearance_case.status is AssessmentStatus.OPENED

    async def test_leaves_the_money_undeclared(
        self, handler: OpenClearanceCaseHandler
    ) -> None:
        clearance_case = await handler.handle(a_command())

        assert clearance_case.declaration_value is None
        assert clearance_case.duty_fee is None

    async def test_persists_the_aggregate(
        self,
        handler: OpenClearanceCaseHandler,
        repository: InMemoryClearanceCaseRepository,
    ) -> None:
        clearance_case = await handler.handle(a_command())

        assert repository.persisted == [clearance_case]

    async def test_gives_every_case_its_own_identity(
        self, handler: OpenClearanceCaseHandler
    ) -> None:
        first = await handler.handle(a_command(shipment_id="s-1"))
        second = await handler.handle(a_command(shipment_id="s-2"))

        assert not first.id.equals(second.id)


class TestMessageHandler:
    def test_subscribes_to_shipment_manifest_finalized(self) -> None:
        assert OpenClearanceCaseMessageHandler.message_type == (
            "ShipmentManifestFinalized"
        )

    def test_names_itself_for_the_inbox(self) -> None:
        assert OpenClearanceCaseMessageHandler.handler_name == (
            "OpenClearanceCaseMessageHandler"
        )

    async def test_opens_a_case_from_a_delivered_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = InMemoryClearanceCaseRepository()
        monkeypatch.setattr(
            "modules.customs_clearance.src.features."
            "open_clearance_case.open_clearance_case_message_handler."
            "PostgresClearanceCaseRepository",
            lambda session: repository,
        )

        envelope = MessageEnvelope(
            message_id=uuid4(),
            message_type="ShipmentManifestFinalized",
            body={
                "shipment_id": "3468ff71-574c-48f1-8af6-fd889d66eeef",
                "waybill_number": "MUST-0000006",
                "commodity_code": "8471",
            },
        )

        await OpenClearanceCaseMessageHandler(session=None).handle(envelope)

        assert len(repository.persisted) == 1
        opened = repository.persisted[0]
        assert opened.shipment_id == "3468ff71-574c-48f1-8af6-fd889d66eeef"
        assert opened.status is AssessmentStatus.OPENED
