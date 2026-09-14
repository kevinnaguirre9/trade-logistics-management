"""Unit tests for the *attach legal document reference* use case."""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import ValidationError

from modules.customs_clearance.src.domain.clearance_case import ClearanceCase
from modules.customs_clearance.src.domain.enums import AssessmentStatus, DocumentType
from modules.customs_clearance.src.domain.exceptions import (
    ClearanceCaseNotFoundError,
    DocumentAlreadyAttachedError,
    DocumentsNotAttachableError,
    InvalidCaseIdError,
)
from modules.customs_clearance.src.domain.value_objects import CaseId
from modules.customs_clearance.src.features.attach_document import (
    AttachDocumentCommand,
    AttachDocumentHandler,
    get_attach_document_handler,
)
from modules.customs_clearance.test.doubles import InMemoryClearanceCaseRepository
from modules.shared.http.exceptions.problem_details import PROBLEM_CONTENT_TYPE

A_FILE_UUID = "7c392d07-85d6-473e-b24f-6382c72cc648"
ANOTHER_FILE_UUID = "1b6b5e3e-0353-42f9-8155-3f1d49346ced"


def make_case(
    status: AssessmentStatus = AssessmentStatus.OPENED,
) -> ClearanceCase:
    """Return a stored clearance case in the requested state."""
    clearance_case = ClearanceCase.open_for_shipment(
        case_id=CaseId.generate(),
        shipment_id="c2a7c69d-487f-4312-8649-00f13842ed16",
    )
    clearance_case.status = status
    return clearance_case


def a_command(
    document_type: str = "COMMERCIAL_INVOICE",
    file_uuid: str = A_FILE_UUID,
) -> AttachDocumentCommand:
    return AttachDocumentCommand(document_type=document_type, file_uuid=file_uuid)


@pytest.fixture
def clearance_case() -> ClearanceCase:
    return make_case()


@pytest.fixture
def repository(clearance_case: ClearanceCase) -> InMemoryClearanceCaseRepository:
    return InMemoryClearanceCaseRepository(clearance_case)


@pytest.fixture
def handler(
    repository: InMemoryClearanceCaseRepository,
) -> AttachDocumentHandler:
    return AttachDocumentHandler(clearance_cases=repository)


class TestCommand:
    def test_reads_the_documented_payload(self) -> None:
        command = a_command()

        assert command.document_type is DocumentType.COMMERCIAL_INVOICE
        assert command.file_uuid == UUID(A_FILE_UUID)

    @pytest.mark.parametrize(
        "document_type", ["INVOICE", "commercial_invoice", "", None]
    )
    def test_rejects_paperwork_customs_does_not_accept(
        self, document_type: object
    ) -> None:
        with pytest.raises(ValidationError):
            a_command(document_type=document_type)  # type: ignore[arg-type]

    @pytest.mark.parametrize("file_uuid", ["not-a-uuid", "", None])
    def test_rejects_a_malformed_file_reference(self, file_uuid: object) -> None:
        with pytest.raises(ValidationError):
            a_command(file_uuid=file_uuid)  # type: ignore[arg-type]

    def test_rejects_a_field_the_caller_invented(self) -> None:
        with pytest.raises(ValidationError):
            AttachDocumentCommand(
                document_type="BILL_OF_LADING",
                file_uuid=A_FILE_UUID,
                s3_url="s3://legacy/invoice.pdf",
            )


class TestHandler:
    async def test_files_the_document_against_the_case(
        self, handler: AttachDocumentHandler, clearance_case: ClearanceCase
    ) -> None:
        updated, document = await handler.handle(str(clearance_case.id), a_command())

        assert document.document_type is DocumentType.COMMERCIAL_INVOICE
        assert document.file_uuid == UUID(A_FILE_UUID)
        assert updated is clearance_case
        assert clearance_case.documents == [document]

    async def test_leaves_the_new_document_unverified(
        self, handler: AttachDocumentHandler, clearance_case: ClearanceCase
    ) -> None:
        _, document = await handler.handle(str(clearance_case.id), a_command())

        assert document.is_verified is False
        assert document.verified_by_inspector_id is None

    async def test_starts_verification_on_the_first_document(
        self, handler: AttachDocumentHandler, clearance_case: ClearanceCase
    ) -> None:
        assert clearance_case.status is AssessmentStatus.OPENED

        updated, _ = await handler.handle(str(clearance_case.id), a_command())

        assert updated.status is AssessmentStatus.DOCUMENT_VERIFICATION

    async def test_keeps_the_status_on_every_document_after_the_first(
        self, handler: AttachDocumentHandler, clearance_case: ClearanceCase
    ) -> None:
        case_id = str(clearance_case.id)
        await handler.handle(case_id, a_command())

        updated, _ = await handler.handle(
            case_id, a_command("BILL_OF_LADING", ANOTHER_FILE_UUID)
        )

        assert updated.status is AssessmentStatus.DOCUMENT_VERIFICATION
        assert len(updated.documents) == 2

    async def test_persists_the_whole_aggregate(
        self,
        handler: AttachDocumentHandler,
        repository: InMemoryClearanceCaseRepository,
        clearance_case: ClearanceCase,
    ) -> None:
        await handler.handle(str(clearance_case.id), a_command())

        assert repository.persisted == [clearance_case]

    async def test_gives_every_document_its_own_identity(
        self, handler: AttachDocumentHandler, clearance_case: ClearanceCase
    ) -> None:
        case_id = str(clearance_case.id)
        _, first = await handler.handle(case_id, a_command())
        _, second = await handler.handle(
            case_id, a_command("BILL_OF_LADING", ANOTHER_FILE_UUID)
        )

        assert first.id != second.id

    async def test_reports_an_unknown_case(
        self, handler: AttachDocumentHandler
    ) -> None:
        with pytest.raises(ClearanceCaseNotFoundError):
            await handler.handle(str(uuid4()), a_command())

    async def test_reports_a_malformed_case_identifier(
        self, handler: AttachDocumentHandler
    ) -> None:
        with pytest.raises(InvalidCaseIdError):
            await handler.handle("not-a-uuid", a_command())

    async def test_refuses_the_same_file_twice(
        self, handler: AttachDocumentHandler, clearance_case: ClearanceCase
    ) -> None:
        case_id = str(clearance_case.id)
        await handler.handle(case_id, a_command())

        with pytest.raises(DocumentAlreadyAttachedError):
            await handler.handle(case_id, a_command("BILL_OF_LADING", A_FILE_UUID))

    @pytest.mark.parametrize(
        "status", [AssessmentStatus.RELEASED, AssessmentStatus.REJECTED]
    )
    async def test_refuses_to_file_against_a_decided_case(
        self, status: AssessmentStatus
    ) -> None:
        decided = make_case(status)
        handler = AttachDocumentHandler(
            clearance_cases=InMemoryClearanceCaseRepository(decided)
        )

        with pytest.raises(DocumentsNotAttachableError):
            await handler.handle(str(decided.id), a_command())


@pytest.fixture
def endpoint(app: FastAPI, handler: AttachDocumentHandler) -> Iterator[None]:
    """Serve the endpoint with the in-memory handler, so no database is used."""
    app.dependency_overrides[get_attach_document_handler] = lambda: handler
    yield
    app.dependency_overrides.pop(get_attach_document_handler, None)


class TestEndpoint:
    async def test_answers_with_the_filed_document(
        self, endpoint: None, client: AsyncClient, clearance_case: ClearanceCase
    ) -> None:
        response = await client.post(
            f"/customs/cases/{clearance_case.id}/documents",
            json={"document_type": "COMMERCIAL_INVOICE", "file_uuid": A_FILE_UUID},
        )

        assert response.status_code == 201

        body = response.json()
        assert body["case_id"] == str(clearance_case.id)
        assert body["status"] == AssessmentStatus.DOCUMENT_VERIFICATION
        assert body["documents_attached"] == 1
        assert body["document"]["document_type"] == "COMMERCIAL_INVOICE"
        assert body["document"]["file_uuid"] == A_FILE_UUID
        assert body["document"]["is_verified"] is False
        assert body["document"]["verified_by_inspector_id"] is None

    async def test_points_at_the_tasks_allowed_next(
        self, endpoint: None, client: AsyncClient, clearance_case: ClearanceCase
    ) -> None:
        response = await client.post(
            f"/customs/cases/{clearance_case.id}/documents",
            json={"document_type": "BILL_OF_LADING", "file_uuid": A_FILE_UUID},
        )

        body = response.json()
        document_id = body["document"]["document_id"]
        links = {link["rel"]: link for link in body["_links"]}

        assert links["verify-document"]["href"] == (
            f"/customs/cases/{clearance_case.id}/documents/{document_id}/verify"
        )
        assert links["attach-document"]["href"] == (
            f"/customs/cases/{clearance_case.id}/documents"
        )

    async def test_reports_an_unknown_case_as_problem_details(
        self, endpoint: None, client: AsyncClient
    ) -> None:
        response = await client.post(
            f"/customs/cases/{uuid4()}/documents",
            json={"document_type": "COMMERCIAL_INVOICE", "file_uuid": A_FILE_UUID},
        )

        assert response.status_code == 404
        assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
        assert response.json()["type"].endswith("/clearance-case-not-found")

    async def test_reports_a_decided_case_as_problem_details(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        released = make_case(AssessmentStatus.RELEASED)
        handler = AttachDocumentHandler(
            clearance_cases=InMemoryClearanceCaseRepository(released)
        )
        app.dependency_overrides[get_attach_document_handler] = lambda: handler

        try:
            response = await client.post(
                f"/customs/cases/{released.id}/documents",
                json={
                    "document_type": "COMMERCIAL_INVOICE",
                    "file_uuid": A_FILE_UUID,
                },
            )
        finally:
            app.dependency_overrides.pop(get_attach_document_handler, None)

        assert response.status_code == 409
        assert response.json()["type"].endswith("/documents-not-attachable")

    async def test_reports_the_same_file_twice_as_problem_details(
        self, endpoint: None, client: AsyncClient, clearance_case: ClearanceCase
    ) -> None:
        payload = {"document_type": "COMMERCIAL_INVOICE", "file_uuid": A_FILE_UUID}
        await client.post(f"/customs/cases/{clearance_case.id}/documents", json=payload)

        response = await client.post(
            f"/customs/cases/{clearance_case.id}/documents", json=payload
        )

        assert response.status_code == 409
        assert response.json()["type"].endswith("/document-already-attached")

    async def test_reports_an_unknown_document_type_as_problem_details(
        self, endpoint: None, client: AsyncClient, clearance_case: ClearanceCase
    ) -> None:
        response = await client.post(
            f"/customs/cases/{clearance_case.id}/documents",
            json={"document_type": "PACKING_LIST", "file_uuid": A_FILE_UUID},
        )

        assert response.status_code == 422
        assert response.json()["type"].endswith("/request-validation-failed")

    async def test_reports_a_malformed_case_identifier_as_problem_details(
        self, endpoint: None, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/customs/cases/not-a-uuid/documents",
            json={"document_type": "COMMERCIAL_INVOICE", "file_uuid": A_FILE_UUID},
        )

        assert response.status_code == 422
        assert response.json()["type"].endswith("/invalid-case-id")
