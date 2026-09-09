"""Unit tests for the *upload file* use case."""

import hashlib
import json
from collections.abc import AsyncIterator, Iterator
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import ValidationError

from modules.files.src.domain.exceptions import (
    FileAlreadyStoredError,
    FileTooLargeError,
    InvalidStorageLocationError,
    UnknownStorageDiskError,
)
from modules.files.src.features.upload_file import (
    UploadFileCommand,
    UploadFileHandler,
    get_upload_file_handler,
)
from modules.files.test.doubles import (
    ContendedStoredFileRepository,
    InMemoryFileStorage,
    InMemoryStoredFileRepository,
    UnwritableStoredFileRepository,
)
from modules.shared.http.exceptions.problem_details import PROBLEM_CONTENT_TYPE

PAYLOAD = b"%PDF-1.7 commercial invoice"
PAYLOAD_CHECKSUM = f"sha256:{hashlib.sha256(PAYLOAD).hexdigest()}"


async def a_stream(payload: bytes = PAYLOAD) -> AsyncIterator[bytes]:
    """Yield an upload the way the controller streams one."""
    yield payload


def a_command(
    disk: str = "local",
    path: str = "customs/clearance-cases",
    name: str = "commercial_invoice.pdf",
    content_type: str = "application/pdf",
    metadata: dict | None = None,
    references: list[dict] | None = None,
) -> UploadFileCommand:
    return UploadFileCommand(
        disk=disk,
        path=path,
        name=name,
        content_type=content_type,
        metadata=metadata or {},
        references=references or [],
    )


A_REFERENCE = {
    "context": "customs",
    "entity_type": "ClearanceCase",
    "entity_id": 1,
    "uuid": "123e4567-e89b-12d3-a456-426614174000",
}


@pytest.fixture
def repository() -> InMemoryStoredFileRepository:
    return InMemoryStoredFileRepository()


@pytest.fixture
def storage() -> InMemoryFileStorage:
    return InMemoryFileStorage("local", "aws")


@pytest.fixture
def handler(
    repository: InMemoryStoredFileRepository,
    storage: InMemoryFileStorage,
) -> UploadFileHandler:
    return UploadFileHandler(files=repository, storage=storage)


class TestCommand:
    def test_reads_the_documented_payload(self) -> None:
        command = a_command(references=[A_REFERENCE])
        reference = command.references[0]

        assert reference.entity_type == "ClearanceCase"
        assert reference.entity_id == 1
        assert reference.context == "customs"
        assert str(reference.uuid) == "123e4567-e89b-12d3-a456-426614174000"

    def test_takes_a_reference_with_no_identifier_at_all(self) -> None:
        command = a_command(
            references=[{"context": "customs", "entity_type": "ClearanceCase"}]
        )

        assert command.references[0].entity_id is None
        assert command.references[0].uuid is None

    def test_takes_no_references_at_all(self) -> None:
        assert a_command().references == []

    def test_refuses_a_client_supplied_reference_record_key(self) -> None:
        with pytest.raises(ValidationError):
            a_command(references=[{**A_REFERENCE, "id": 1}])

    def test_defaults_the_path_to_the_root_of_the_disk(self) -> None:
        assert UploadFileCommand(disk="local", name="a.pdf").path == ""

    @pytest.mark.parametrize(
        "reference",
        [
            {"entity_id": 1, "context": "customs"},
            {"entity_id": 1, "entity_type": "ClearanceCase"},
            {"entity_id": 1, "entity_type": "ClearanceCase", "context": ""},
            {"entity_type": "", "context": "customs"},
        ],
    )
    def test_rejects_a_reference_that_does_not_say_what_it_is_about(
        self, reference: dict
    ) -> None:
        with pytest.raises(ValidationError):
            a_command(references=[reference])

    def test_rejects_a_field_the_caller_invented(self) -> None:
        with pytest.raises(ValidationError):
            UploadFileCommand(disk="local", name="a.pdf", bucket="mine")


class TestHandler:
    async def test_stores_the_bytes_on_the_named_disk(
        self, handler: UploadFileHandler, storage: InMemoryFileStorage
    ) -> None:
        await handler.handle(a_command(), a_stream())

        key = "customs/clearance-cases/commercial_invoice.pdf"
        assert storage.objects[("local", key)] == PAYLOAD

    async def test_records_what_was_written_not_what_was_claimed(
        self, handler: UploadFileHandler
    ) -> None:
        stored_file = await handler.handle(a_command(), a_stream())

        assert stored_file.size_bytes == len(PAYLOAD)
        assert stored_file.checksum == PAYLOAD_CHECKSUM

    async def test_persists_the_aggregate(
        self, handler: UploadFileHandler, repository: InMemoryStoredFileRepository
    ) -> None:
        stored_file = await handler.handle(a_command(), a_stream())

        assert repository.persisted == [stored_file]

    async def test_attaches_the_owning_aggregates(
        self, handler: UploadFileHandler
    ) -> None:
        stored_file = await handler.handle(
            a_command(references=[A_REFERENCE]), a_stream()
        )

        assert stored_file.is_referenced_by("customs", "ClearanceCase", "1")
        assert str(stored_file.references[0].entity_uuid) == (
            "123e4567-e89b-12d3-a456-426614174000"
        )

    async def test_gives_every_upload_its_own_identity(
        self, handler: UploadFileHandler
    ) -> None:
        first = await handler.handle(a_command(name="a.pdf"), a_stream())
        second = await handler.handle(a_command(name="b.pdf"), a_stream())

        assert not first.id.equals(second.id)

    async def test_refuses_a_disk_this_deployment_has_not_configured(
        self, handler: UploadFileHandler
    ) -> None:
        with pytest.raises(UnknownStorageDiskError):
            await handler.handle(a_command(disk="gcp"), a_stream())

    async def test_refuses_to_overwrite_an_existing_object(
        self, handler: UploadFileHandler
    ) -> None:
        await handler.handle(a_command(), a_stream())

        with pytest.raises(FileAlreadyStoredError):
            await handler.handle(a_command(), a_stream())

    async def test_refuses_a_path_that_climbs_out_of_the_disk(
        self, handler: UploadFileHandler
    ) -> None:
        with pytest.raises(InvalidStorageLocationError):
            await handler.handle(a_command(path="customs/../../etc"), a_stream())

    async def test_stops_an_upload_that_outgrows_the_ceiling(
        self, repository: InMemoryStoredFileRepository
    ) -> None:
        handler = UploadFileHandler(
            files=repository,
            storage=InMemoryFileStorage("local", max_upload_bytes=8),
        )

        with pytest.raises(FileTooLargeError):
            await handler.handle(a_command(), a_stream(b"x" * 9))

        assert repository.persisted == []

    async def test_takes_the_object_back_out_when_the_row_cannot_be_written(
        self, storage: InMemoryFileStorage
    ) -> None:
        handler = UploadFileHandler(
            files=UnwritableStoredFileRepository(), storage=storage
        )

        with pytest.raises(RuntimeError):
            await handler.handle(a_command(), a_stream())

        assert storage.objects == {}

    async def test_leaves_the_object_alone_when_it_loses_the_race_for_the_key(
        self, storage: InMemoryFileStorage
    ) -> None:
        handler = UploadFileHandler(
            files=ContendedStoredFileRepository(), storage=storage
        )

        with pytest.raises(FileAlreadyStoredError):
            await handler.handle(a_command(), a_stream())

        # The object at that key belongs to whoever won the race.
        key = "customs/clearance-cases/commercial_invoice.pdf"
        assert storage.objects[("local", key)] == PAYLOAD


@pytest.fixture
def endpoint(app: FastAPI, handler: UploadFileHandler) -> Iterator[None]:
    """Serve the endpoint with the in-memory handler, so no database is used."""
    app.dependency_overrides[get_upload_file_handler] = lambda: handler
    yield
    app.dependency_overrides.pop(get_upload_file_handler, None)


class TestEndpoint:
    async def test_answers_with_the_stored_file(
        self, endpoint: None, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/files",
            files={"file": ("commercial_invoice.pdf", PAYLOAD, "application/pdf")},
            data={
                "disk": "local",
                "path": "customs/clearance-cases",
                "name": "commercial_invoice.pdf",
                "metadata": json.dumps({"issued_by": "ACME Freight"}),
                "references": json.dumps([A_REFERENCE]),
            },
        )

        assert response.status_code == 201

        body = response.json()
        assert body["disk"] == "local"
        assert body["key"] == "customs/clearance-cases/commercial_invoice.pdf"
        assert body["size_bytes"] == len(PAYLOAD)
        assert body["checksum"] == PAYLOAD_CHECKSUM
        assert body["content_type"] == "application/pdf"
        assert body["metadata"] == {"issued_by": "ACME Freight"}
        assert uuid4().__class__(body["file_uuid"])

    async def test_returns_the_references_it_recorded(
        self, endpoint: None, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/files",
            files={"file": ("invoice.pdf", PAYLOAD, "application/pdf")},
            data={"path": "customs", "references": json.dumps([A_REFERENCE])},
        )

        reference = response.json()["references"][0]
        assert reference["context"] == "customs"
        assert reference["entity_type"] == "ClearanceCase"
        assert reference["entity_id"] == "1"

    async def test_stores_a_file_nobody_declared_a_reference_for(
        self, endpoint: None, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/files",
            files={"file": ("invoice.pdf", PAYLOAD, "application/pdf")},
            data={"path": "customs"},
        )

        assert response.status_code == 201
        assert response.json()["references"] == []

    async def test_records_a_reference_with_no_identifier(
        self, endpoint: None, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/files",
            files={"file": ("tariff_schedule.pdf", PAYLOAD, "application/pdf")},
            data={
                "path": "customs",
                "references": json.dumps(
                    [{"context": "customs", "entity_type": "TariffSchedule"}]
                ),
            },
        )

        assert response.status_code == 201

        reference = response.json()["references"][0]
        assert reference["entity_type"] == "TariffSchedule"
        assert reference["entity_id"] is None
        assert reference["entity_uuid"] is None

    async def test_refuses_a_client_supplied_reference_record_key(
        self, endpoint: None, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/files",
            files={"file": ("invoice.pdf", PAYLOAD, "application/pdf")},
            data={
                "path": "customs",
                "references": json.dumps([{**A_REFERENCE, "id": 1}]),
            },
        )

        assert response.status_code == 422
        assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)

    async def test_falls_back_to_the_uploaded_part_for_the_name(
        self, endpoint: None, client: AsyncClient, storage: InMemoryFileStorage
    ) -> None:
        response = await client.post(
            "/files",
            files={"file": ("packing_list.pdf", PAYLOAD, "application/pdf")},
            data={"path": "customs"},
        )

        assert response.json()["name"] == "packing_list.pdf"
        assert ("local", "customs/packing_list.pdf") in storage.objects

    async def test_reports_a_malformed_json_part_as_problem_details(
        self, endpoint: None, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/files",
            files={"file": ("invoice.pdf", PAYLOAD, "application/pdf")},
            data={"path": "customs", "references": "{not json"},
        )

        assert response.status_code == 422
        assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
        assert response.json()["type"].endswith("/invalid-upload-payload")

    async def test_reports_an_unknown_disk_as_problem_details(
        self, endpoint: None, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/files",
            files={"file": ("invoice.pdf", PAYLOAD, "application/pdf")},
            data={"disk": "gcp", "path": "customs"},
        )

        assert response.status_code == 422
        assert response.json()["type"].endswith("/unknown-storage-disk")
        assert response.json()["configured_disks"] == ["local", "aws"]

    async def test_reports_a_traversing_path_as_problem_details(
        self, endpoint: None, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/files",
            files={"file": ("invoice.pdf", PAYLOAD, "application/pdf")},
            data={"path": "../../etc"},
        )

        assert response.status_code == 422
        assert response.json()["type"].endswith("/invalid-storage-location")

    async def test_reports_a_collision_as_problem_details(
        self, endpoint: None, client: AsyncClient
    ) -> None:
        for _ in range(2):
            response = await client.post(
                "/files",
                files={"file": ("invoice.pdf", PAYLOAD, "application/pdf")},
                data={"path": "customs"},
            )

        assert response.status_code == 409
        assert response.json()["type"].endswith("/file-already-stored")
