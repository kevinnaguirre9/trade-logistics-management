"""Unit tests for the *verify document* use case."""

from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import ValidationError

from modules.customs_clearance.src.domain.clearance_case import ClearanceCase
from modules.customs_clearance.src.domain.enums import AssessmentStatus
from modules.customs_clearance.src.domain.events import DocumentVerificationCompleted
from modules.customs_clearance.src.domain.exceptions import (
    ClearanceCaseNotFoundError,
    DocumentAlreadyVerifiedError,
    DocumentNotFoundError,
    DocumentNotVerifiableError,
    InvalidCaseIdError,
)
from modules.customs_clearance.src.domain.value_objects import CaseId
from modules.customs_clearance.src.features.verify_document import (
    VerifyDocumentCommand,
    VerifyDocumentHandler,
    get_verify_document_handler,
)
from modules.customs_clearance.test.doubles import InMemoryClearanceCaseRepository
from modules.shared.http.exceptions.problem_details import PROBLEM_CONTENT_TYPE
from modules.shared.message_bus import IntegrationMessage

AN_INSPECTOR = "INSP-4471"


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


def make_case(
    document_types: tuple[str, ...] = ("COMMERCIAL_INVOICE", "BILL_OF_LADING"),
    status: AssessmentStatus | None = None,
) -> ClearanceCase:
    """Return a case with the given documents filed but none of them cleared."""
    clearance_case = ClearanceCase.open_for_shipment(
        case_id=CaseId.generate(),
        shipment_id="c2a7c69d-487f-4312-8649-00f13842ed16",
    )
    for document_type in document_types:
        clearance_case.attach_document(document_type, uuid4())

    if status is not None:
        clearance_case.status = status
    return clearance_case


@pytest.fixture
def clearance_case() -> ClearanceCase:
    return make_case()


@pytest.fixture
def outbox() -> InMemoryOutbox:
    return InMemoryOutbox()


@pytest.fixture
def handler(
    clearance_case: ClearanceCase, outbox: InMemoryOutbox
) -> VerifyDocumentHandler:
    return VerifyDocumentHandler(
        clearance_cases=InMemoryClearanceCaseRepository(clearance_case),
        outbox=outbox,
    )


def a_command(inspector_id: str = AN_INSPECTOR) -> VerifyDocumentCommand:
    return VerifyDocumentCommand(inspector_id=inspector_id)


class TestCommand:
    def test_reads_the_documented_payload(self) -> None:
        assert a_command().inspector_id == AN_INSPECTOR

    def test_trims_the_inspector_identifier(self) -> None:
        assert a_command("  INSP-1  ").inspector_id == "INSP-1"

    @pytest.mark.parametrize("inspector_id", ["", "   ", None, 7, "x" * 129])
    def test_requires_an_identified_inspector(self, inspector_id: object) -> None:
        with pytest.raises(ValidationError):
            a_command(inspector_id)  # type: ignore[arg-type]

    def test_rejects_a_field_the_caller_invented(self) -> None:
        with pytest.raises(ValidationError):
            VerifyDocumentCommand(inspector_id=AN_INSPECTOR, approved=True)


class TestHandler:
    async def test_records_the_sign_off(
        self, handler: VerifyDocumentHandler, clearance_case: ClearanceCase
    ) -> None:
        document = clearance_case.documents[0]

        _, cleared = await handler.handle(
            str(clearance_case.id), document.id, a_command()
        )

        assert cleared.is_verified is True
        assert cleared.verified_by_inspector_id == AN_INSPECTOR

    async def test_queues_nothing_while_paperwork_is_outstanding(
        self,
        handler: VerifyDocumentHandler,
        clearance_case: ClearanceCase,
        outbox: InMemoryOutbox,
    ) -> None:
        updated, _ = await handler.handle(
            str(clearance_case.id), clearance_case.documents[0].id, a_command()
        )

        assert updated.status is AssessmentStatus.DOCUMENT_VERIFICATION
        assert outbox.scheduled == []

    async def test_moves_to_risk_assessment_on_the_last_document(
        self,
        handler: VerifyDocumentHandler,
        clearance_case: ClearanceCase,
        outbox: InMemoryOutbox,
    ) -> None:
        case_id = str(clearance_case.id)
        for document in list(clearance_case.documents):
            updated, _ = await handler.handle(case_id, document.id, a_command())

        assert updated.status is AssessmentStatus.RISK_ASSESSMENT
        assert len(outbox.scheduled) == 1

        event = outbox.scheduled[0]
        assert isinstance(event, DocumentVerificationCompleted)
        assert event.case_id == case_id
        assert event.shipment_id == clearance_case.shipment_id

    async def test_announces_completion_only_once(self, outbox: InMemoryOutbox) -> None:
        # A third document, filed and cleared after the case already moved on.
        clearance_case = make_case()
        handler = VerifyDocumentHandler(
            clearance_cases=InMemoryClearanceCaseRepository(clearance_case),
            outbox=outbox,
        )
        case_id = str(clearance_case.id)
        for document in list(clearance_case.documents):
            await handler.handle(case_id, document.id, a_command())

        extra = clearance_case.attach_document("COMMERCIAL_INVOICE", uuid4())
        await handler.handle(case_id, extra.id, a_command())

        assert len(outbox.scheduled) == 1

    async def test_persists_the_whole_aggregate(
        self, clearance_case: ClearanceCase, outbox: InMemoryOutbox
    ) -> None:
        repository = InMemoryClearanceCaseRepository(clearance_case)
        handler = VerifyDocumentHandler(clearance_cases=repository, outbox=outbox)

        await handler.handle(
            str(clearance_case.id), clearance_case.documents[0].id, a_command()
        )

        assert repository.persisted == [clearance_case]

    async def test_reports_an_unknown_case(
        self, handler: VerifyDocumentHandler
    ) -> None:
        with pytest.raises(ClearanceCaseNotFoundError):
            await handler.handle(str(uuid4()), uuid4(), a_command())

    async def test_reports_a_malformed_case_identifier(
        self, handler: VerifyDocumentHandler
    ) -> None:
        with pytest.raises(InvalidCaseIdError):
            await handler.handle("not-a-uuid", uuid4(), a_command())

    async def test_reports_a_document_the_case_does_not_hold(
        self, handler: VerifyDocumentHandler, clearance_case: ClearanceCase
    ) -> None:
        with pytest.raises(DocumentNotFoundError):
            await handler.handle(str(clearance_case.id), uuid4(), a_command())

    async def test_refuses_to_clear_the_same_document_twice(
        self, handler: VerifyDocumentHandler, clearance_case: ClearanceCase
    ) -> None:
        case_id = str(clearance_case.id)
        document_id = clearance_case.documents[0].id
        await handler.handle(case_id, document_id, a_command())

        with pytest.raises(DocumentAlreadyVerifiedError):
            await handler.handle(case_id, document_id, a_command("INSP-9999"))

    @pytest.mark.parametrize(
        "status", [AssessmentStatus.RELEASED, AssessmentStatus.REJECTED]
    )
    async def test_refuses_to_clear_on_a_decided_case(
        self, status: AssessmentStatus, outbox: InMemoryOutbox
    ) -> None:
        decided = make_case(status=status)
        handler = VerifyDocumentHandler(
            clearance_cases=InMemoryClearanceCaseRepository(decided),
            outbox=outbox,
        )

        with pytest.raises(DocumentNotVerifiableError):
            await handler.handle(str(decided.id), decided.documents[0].id, a_command())


@pytest.fixture
def endpoint(app: FastAPI, handler: VerifyDocumentHandler) -> Iterator[None]:
    """Serve the endpoint with the in-memory handler, so no database is used."""
    app.dependency_overrides[get_verify_document_handler] = lambda: handler
    yield
    app.dependency_overrides.pop(get_verify_document_handler, None)


class TestEndpoint:
    async def test_answers_with_the_cleared_document(
        self, endpoint: None, client: AsyncClient, clearance_case: ClearanceCase
    ) -> None:
        document = clearance_case.documents[0]

        response = await client.post(
            f"/customs/cases/{clearance_case.id}/documents/{document.id}/verify",
            json={"inspector_id": AN_INSPECTOR},
        )

        assert response.status_code == 200

        body = response.json()
        assert body["status"] == AssessmentStatus.DOCUMENT_VERIFICATION
        assert body["documents_verified"] == 1
        assert body["paperwork_complete"] is False
        assert body["document"]["is_verified"] is True
        assert body["document"]["verified_by_inspector_id"] == AN_INSPECTOR

    async def test_reports_the_case_moving_to_risk_assessment(
        self, endpoint: None, client: AsyncClient, clearance_case: ClearanceCase
    ) -> None:
        for document in list(clearance_case.documents):
            response = await client.post(
                f"/customs/cases/{clearance_case.id}/documents/{document.id}/verify",
                json={"inspector_id": AN_INSPECTOR},
            )

        body = response.json()
        assert body["status"] == AssessmentStatus.RISK_ASSESSMENT
        assert body["paperwork_complete"] is True
        assert body["documents_verified"] == 2
        # Nothing further is asked of the caller: the risk assessment runs off
        # the queued event.
        assert body["_links"] == []

    async def test_reports_an_unknown_document_as_problem_details(
        self, endpoint: None, client: AsyncClient, clearance_case: ClearanceCase
    ) -> None:
        response = await client.post(
            f"/customs/cases/{clearance_case.id}/documents/{uuid4()}/verify",
            json={"inspector_id": AN_INSPECTOR},
        )

        assert response.status_code == 404
        assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
        assert response.json()["type"].endswith("/document-not-found")

    async def test_reports_a_second_sign_off_as_problem_details(
        self, endpoint: None, client: AsyncClient, clearance_case: ClearanceCase
    ) -> None:
        url = (
            f"/customs/cases/{clearance_case.id}"
            f"/documents/{clearance_case.documents[0].id}/verify"
        )
        await client.post(url, json={"inspector_id": AN_INSPECTOR})

        response = await client.post(url, json={"inspector_id": "INSP-9999"})

        assert response.status_code == 409
        assert response.json()["type"].endswith("/document-already-verified")

    async def test_reports_a_malformed_document_identifier(
        self, endpoint: None, client: AsyncClient, clearance_case: ClearanceCase
    ) -> None:
        response = await client.post(
            f"/customs/cases/{clearance_case.id}/documents/not-a-uuid/verify",
            json={"inspector_id": AN_INSPECTOR},
        )

        assert response.status_code == 422
        assert response.json()["type"].endswith("/request-validation-failed")

    async def test_reports_a_missing_inspector_as_problem_details(
        self, endpoint: None, client: AsyncClient, clearance_case: ClearanceCase
    ) -> None:
        response = await client.post(
            f"/customs/cases/{clearance_case.id}"
            f"/documents/{clearance_case.documents[0].id}/verify",
            json={"inspector_id": "  "},
        )

        assert response.status_code == 422
        assert response.json()["type"].endswith("/request-validation-failed")
