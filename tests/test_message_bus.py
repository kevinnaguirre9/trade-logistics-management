"""Unit tests for the shared message bus."""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest

from modules.shared.message_bus.cli.registry import ModuleBinding, ModuleRegistry
from modules.shared.message_bus.errors import (
    MessageHandlingError,
    UnknownMessageDestinationError,
    UnknownModuleError,
)
from modules.shared.message_bus.handlers import MessageHandler, MessageHandlerRegistry
from modules.shared.message_bus.inbox.dispatcher import InboxMessageDispatcher
from modules.shared.message_bus.messages import (
    REDELIVERY_COUNT_HEADER,
    IntegrationMessage,
    MessageDestination,
    MessageDestinationRegistry,
    MessageEnvelope,
)
from modules.shared.message_bus.outbox.outbox_message import (
    OutboxMessage,
    OutboxStatus,
)
from modules.shared.message_bus.rabbitmq.config import BrokerTopology


@dataclass(frozen=True, slots=True)
class ShipmentManifestFinalized(IntegrationMessage):
    """A sample contract, named after the behaviour that produced it."""

    shipment_id: str
    waybill_number: str
    commodity_code: str


def make_envelope(
    message_type: str = "ShipmentManifestFinalized",
    headers: dict[str, Any] | None = None,
) -> MessageEnvelope:
    return MessageEnvelope(
        message_id=uuid4(),
        message_type=message_type,
        body={"shipment_id": "s-1"},
        headers=headers or {},
    )


class TestIntegrationMessage:
    def test_defaults_the_type_to_the_class_name(self) -> None:
        assert ShipmentManifestFinalized.message_type == "ShipmentManifestFinalized"

    def test_round_trips_through_its_body(self) -> None:
        message = ShipmentManifestFinalized(
            shipment_id="s-1",
            waybill_number="MUST-0000001",
            commodity_code="8471",
        )

        assert ShipmentManifestFinalized.from_body(message.to_body()) == message

    def test_ignores_fields_added_by_a_newer_publisher(self) -> None:
        body = {
            "shipment_id": "s-1",
            "waybill_number": "MUST-0000001",
            "commodity_code": "8471",
            "declared_value": 100,
        }

        rebuilt = ShipmentManifestFinalized.from_body(body)

        assert rebuilt.shipment_id == "s-1"


class TestMessageDestinationRegistry:
    def test_resolves_a_registered_destination(self) -> None:
        registry = MessageDestinationRegistry()
        destination = MessageDestination("trade-logistics.topic", "shipment.manifest")

        registry.register(ShipmentManifestFinalized, destination)

        assert registry.destination_for(ShipmentManifestFinalized) is destination
        assert registry.destination_for("ShipmentManifestFinalized") is destination

    def test_rejects_an_unregistered_message_type(self) -> None:
        with pytest.raises(UnknownMessageDestinationError):
            MessageDestinationRegistry().destination_for("NeverRegistered")


class TestOutboxMessage:
    def test_schedules_a_message_as_pending(self) -> None:
        row = OutboxMessage.schedule(
            message=ShipmentManifestFinalized("s-1", "MUST-0000001", "8471"),
            destination=MessageDestination("exchange", "routing.key"),
        )

        assert row.status is OutboxStatus.PENDING
        assert row.message_type == "ShipmentManifestFinalized"
        assert row.exchange == "exchange"
        assert row.routing_key == "routing.key"
        assert row.body["waybill_number"] == "MUST-0000001"
        assert row.sent_at is None

    def test_marks_the_message_as_sent(self) -> None:
        row = OutboxMessage.schedule(
            message=ShipmentManifestFinalized("s-1", "MUST-0000001", "8471"),
            destination=MessageDestination("exchange", "routing.key"),
        )

        row.mark_as_sent()

        assert row.is_sent
        assert row.sent_at is not None


class TestMessageHandlerRegistry:
    def test_subscribes_a_handler_to_its_message_type(self) -> None:
        class OpenClearanceCase(MessageHandler):
            message_type = "ShipmentManifestFinalized"

            async def handle(self, envelope: MessageEnvelope) -> None:
                return None

        registry = MessageHandlerRegistry()
        registry.register(OpenClearanceCase)

        assert registry.handlers_for("ShipmentManifestFinalized") == (
            OpenClearanceCase,
        )
        assert registry.subscribed_types() == ("ShipmentManifestFinalized",)
        assert OpenClearanceCase.handler_name == "OpenClearanceCase"

    def test_ignores_a_repeated_registration(self) -> None:
        class Twice(MessageHandler):
            message_type = "ShipmentManifestFinalized"

            async def handle(self, envelope: MessageEnvelope) -> None:
                return None

        registry = MessageHandlerRegistry()
        registry.register_all(Twice, Twice)

        assert registry.handlers_for("ShipmentManifestFinalized") == (Twice,)


class FakeSession:
    """Stands in for an AsyncSession, recording how it was closed."""

    def __init__(self, inbox: set[tuple[UUID, str]]) -> None:
        self.inbox = inbox
        self.committed = False
        self.rolled_back = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class FakeInboxRepository:
    """Reads and writes the deduplication keys held by the fake session."""

    def __init__(self, session: FakeSession) -> None:
        self._session = session

    async def was_handled(self, message_id: UUID, handler_name: str) -> bool:
        return (message_id, handler_name) in self._session.inbox

    async def record(
        self, message_id: UUID, message_type: str, handler_name: str
    ) -> None:
        self._session.inbox.add((message_id, handler_name))


@pytest.fixture
def inbox_rows() -> set[tuple[UUID, str]]:
    return set()


@pytest.fixture
def sessions(inbox_rows: set[tuple[UUID, str]]) -> list[FakeSession]:
    return []


@pytest.fixture
def session_factory(
    inbox_rows: set[tuple[UUID, str]],
    sessions: list[FakeSession],
    monkeypatch: pytest.MonkeyPatch,
):
    """Hand the dispatcher fake sessions and a fake inbox repository."""
    monkeypatch.setattr(
        "modules.shared.message_bus.inbox.dispatcher.InboxMessageRepository",
        FakeInboxRepository,
    )

    @asynccontextmanager
    async def factory():
        session = FakeSession(inbox_rows)
        sessions.append(session)
        yield session

    return factory


class TestInboxMessageDispatcher:
    async def test_runs_the_handler_and_records_it(
        self, session_factory, inbox_rows: set[tuple[UUID, str]]
    ) -> None:
        calls: list[MessageEnvelope] = []

        class RecordingHandler(MessageHandler):
            message_type = "ShipmentManifestFinalized"

            async def handle(self, envelope: MessageEnvelope) -> None:
                calls.append(envelope)

        registry = MessageHandlerRegistry()
        registry.register(RecordingHandler)
        dispatcher = InboxMessageDispatcher(session_factory, registry)
        envelope = make_envelope()

        await dispatcher.dispatch(envelope)

        assert len(calls) == 1
        assert (envelope.message_id, "RecordingHandler") in inbox_rows

    async def test_skips_a_message_already_handled(
        self, session_factory, inbox_rows: set[tuple[UUID, str]]
    ) -> None:
        calls: list[MessageEnvelope] = []

        class OnceHandler(MessageHandler):
            message_type = "ShipmentManifestFinalized"

            async def handle(self, envelope: MessageEnvelope) -> None:
                calls.append(envelope)

        registry = MessageHandlerRegistry()
        registry.register(OnceHandler)
        dispatcher = InboxMessageDispatcher(session_factory, registry)
        envelope = make_envelope()

        await dispatcher.dispatch(envelope)
        await dispatcher.dispatch(envelope)

        assert len(calls) == 1

    async def test_retries_a_failing_handler_in_place(self, session_factory) -> None:
        attempts: list[int] = []

        class FlakyHandler(MessageHandler):
            message_type = "ShipmentManifestFinalized"

            async def handle(self, envelope: MessageEnvelope) -> None:
                attempts.append(1)
                if len(attempts) < 3:
                    raise RuntimeError("transient")

        registry = MessageHandlerRegistry()
        registry.register(FlakyHandler)
        dispatcher = InboxMessageDispatcher(
            session_factory, registry, immediate_retries=3
        )

        await dispatcher.dispatch(make_envelope())

        assert len(attempts) == 3

    async def test_reports_a_handler_that_never_succeeds(
        self, session_factory, sessions: list[FakeSession]
    ) -> None:
        class BrokenHandler(MessageHandler):
            message_type = "ShipmentManifestFinalized"

            async def handle(self, envelope: MessageEnvelope) -> None:
                raise RuntimeError("permanent")

        registry = MessageHandlerRegistry()
        registry.register(BrokenHandler)
        dispatcher = InboxMessageDispatcher(
            session_factory, registry, immediate_retries=2
        )

        with pytest.raises(MessageHandlingError) as failure:
            await dispatcher.dispatch(make_envelope())

        assert len(failure.value.failures) == 1
        # One attempt plus two immediate retries, each rolled back.
        assert len(sessions) == 3
        assert all(session.rolled_back for session in sessions)

    async def test_one_failing_handler_does_not_undo_the_others(
        self, session_factory, inbox_rows: set[tuple[UUID, str]]
    ) -> None:
        class GoodHandler(MessageHandler):
            message_type = "ShipmentManifestFinalized"

            async def handle(self, envelope: MessageEnvelope) -> None:
                return None

        class BadHandler(MessageHandler):
            message_type = "ShipmentManifestFinalized"

            async def handle(self, envelope: MessageEnvelope) -> None:
                raise RuntimeError("nope")

        registry = MessageHandlerRegistry()
        registry.register_all(GoodHandler, BadHandler)
        dispatcher = InboxMessageDispatcher(
            session_factory, registry, immediate_retries=0
        )
        envelope = make_envelope()

        with pytest.raises(MessageHandlingError):
            await dispatcher.dispatch(envelope)

        assert (envelope.message_id, "GoodHandler") in inbox_rows
        assert (envelope.message_id, "BadHandler") not in inbox_rows

    async def test_ignores_a_type_nobody_subscribed_to(
        self, session_factory, sessions: list[FakeSession]
    ) -> None:
        dispatcher = InboxMessageDispatcher(session_factory, MessageHandlerRegistry())

        await dispatcher.dispatch(make_envelope("SomethingElse"))

        assert sessions == []


class TestMessageEnvelope:
    def test_reads_the_redelivery_counter(self) -> None:
        envelope = make_envelope(headers={REDELIVERY_COUNT_HEADER: 2})

        assert envelope.redelivery_count == 2

    @pytest.mark.parametrize("header", [{}, {REDELIVERY_COUNT_HEADER: None}])
    def test_defaults_the_counter_to_zero(self, header: dict[str, Any]) -> None:
        assert make_envelope(headers=header).redelivery_count == 0


class TestBrokerTopology:
    def test_keeps_the_environment_value_when_no_override_is_given(self) -> None:
        topology = BrokerTopology.from_settings()

        overridden = topology.overridden_with(primary_queue=None, delayed_retries=None)

        assert overridden.primary_queue == topology.primary_queue
        assert overridden.delayed_retries == topology.delayed_retries

    def test_applies_the_overrides_it_is_given(self) -> None:
        topology = BrokerTopology.from_settings()

        overridden = topology.overridden_with(
            primary_queue="trade-logistics.customs",
            delayed_retries=7,
        )

        assert overridden.primary_queue == "trade-logistics.customs"
        assert overridden.delayed_retries == 7

    def test_exposes_the_retry_delay_in_seconds(self) -> None:
        topology = BrokerTopology.from_settings().overridden_with(
            retry_message_ttl_ms=2_500
        )

        assert topology.retry_delay_seconds == 2.5


class TestModuleRegistry:
    def test_resolves_a_known_module(self) -> None:
        registry = ModuleRegistry(ModuleBinding(name="shipment", schema="shipment"))

        assert registry.get("shipment").schema == "shipment"
        assert registry.names() == ("shipment",)

    def test_rejects_an_unknown_module(self) -> None:
        registry = ModuleRegistry(ModuleBinding(name="shipment", schema="shipment"))

        with pytest.raises(UnknownModuleError):
            registry.get("nope")
