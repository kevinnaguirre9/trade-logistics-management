"""Unit tests for the Files domain model."""

from uuid import UUID, uuid4

import pytest

from modules.files.src.domain.entities import FileReference
from modules.files.src.domain.exceptions import (
    InvalidFileIdError,
    InvalidFileReferenceError,
    InvalidStorageLocationError,
    InvalidStoredFileError,
)
from modules.files.src.domain.stored_file import (
    DEFAULT_CONTENT_TYPE,
    StoredFile,
)
from modules.files.src.domain.value_objects import FileId, StorageLocation


def a_location(
    path: str = "customs/clearance-cases",
    name: str = "commercial_invoice.pdf",
) -> StorageLocation:
    return StorageLocation(path=path, name=name)


def a_reference(
    entity_type: str = "ClearanceCase",
    entity_id: object = 1,
    context: str = "customs",
    entity_uuid: object = None,
) -> FileReference:
    return FileReference.declare(
        entity_type=entity_type,
        entity_id=entity_id,
        context=context,
        entity_uuid=entity_uuid,
    )


def a_file(
    disk: str = "local",
    size_bytes: int = 2048,
    content_type: str = "application/pdf",
    metadata: dict | None = None,
    references: list[FileReference] | None = None,
) -> StoredFile:
    return StoredFile.register(
        file_id=FileId.generate(),
        disk=disk,
        location=a_location(),
        size_bytes=size_bytes,
        content_type=content_type,
        checksum="sha256:abc",
        metadata=metadata,
        references=references,
    )


class TestFileId:
    def test_accepts_a_uuid(self) -> None:
        value = uuid4()

        assert FileId(value).value == value

    def test_accepts_the_string_form(self) -> None:
        value = uuid4()

        assert FileId(str(value)).value == value

    @pytest.mark.parametrize("value", ["not-a-uuid", "", 42, None])
    def test_rejects_anything_else(self, value: object) -> None:
        with pytest.raises(InvalidFileIdError):
            FileId(value)  # type: ignore[arg-type]

    def test_compares_by_value(self) -> None:
        value = uuid4()

        assert FileId(value).equals(FileId(value))
        assert not FileId(value).equals(FileId.generate())

    def test_exposes_its_column_value(self) -> None:
        value = uuid4()

        assert FileId(value).__composite_values__() == (value,)

    def test_generates_a_unique_identity(self) -> None:
        assert isinstance(FileId.generate().value, UUID)
        assert FileId.generate() != FileId.generate()


class TestStorageLocation:
    def test_joins_the_path_and_the_name_into_a_key(self) -> None:
        assert a_location().key == "customs/clearance-cases/commercial_invoice.pdf"

    def test_keys_a_file_at_the_root_by_its_name_alone(self) -> None:
        assert StorageLocation(path="", name="invoice.pdf").key == "invoice.pdf"

    @pytest.mark.parametrize(
        "path",
        ["/customs/cases/", "customs//cases", "  customs/cases  ", "customs\\cases"],
    )
    def test_normalizes_the_path(self, path: str) -> None:
        assert StorageLocation(path=path, name="a.pdf").path == "customs/cases"

    @pytest.mark.parametrize(
        "path",
        ["../etc", "customs/../../etc", "customs/./cases", "..", "~/keys"],
    )
    def test_refuses_to_climb_out_of_the_disk(self, path: str) -> None:
        with pytest.raises(InvalidStorageLocationError):
            StorageLocation(path=path, name="a.pdf")

    def test_refuses_a_windows_absolute_path(self) -> None:
        with pytest.raises(InvalidStorageLocationError):
            StorageLocation(path="C:/secrets", name="a.pdf")

    @pytest.mark.parametrize("name", ["", "   ", "a/b.pdf", "a\\b.pdf", "..", None, 7])
    def test_rejects_a_name_that_is_not_a_name(self, name: object) -> None:
        with pytest.raises(InvalidStorageLocationError):
            StorageLocation(path="customs", name=name)  # type: ignore[arg-type]

    def test_rejects_a_nul_byte(self) -> None:
        with pytest.raises(InvalidStorageLocationError):
            StorageLocation(path="customs", name="a\x00.pdf")

    def test_rejects_an_overlong_name(self) -> None:
        with pytest.raises(InvalidStorageLocationError):
            StorageLocation(path="customs", name="a" * 256)

    def test_reads_its_extension(self) -> None:
        assert a_location(name="invoice.PDF").extension == "pdf"
        assert a_location(name="invoice").extension == ""

    def test_exposes_its_column_values(self) -> None:
        assert a_location().__composite_values__() == (
            "customs/clearance-cases",
            "commercial_invoice.pdf",
        )

    def test_compares_by_value(self) -> None:
        assert a_location() == a_location()


class TestFileReference:
    def test_keeps_both_identifiers_of_the_owner(self) -> None:
        entity_uuid = uuid4()

        reference = a_reference(entity_id=1, entity_uuid=entity_uuid)

        assert reference.entity_id == "1"
        assert reference.entity_uuid == entity_uuid

    def test_accepts_a_uuid_in_string_form(self) -> None:
        entity_uuid = uuid4()

        assert a_reference(entity_uuid=str(entity_uuid)).entity_uuid == entity_uuid

    def test_leaves_the_owner_uuid_unset_when_the_context_has_none(self) -> None:
        assert a_reference().entity_uuid is None

    @pytest.mark.parametrize("entity_id", [None, "", "   "])
    def test_describes_something_with_no_identifier_of_its_own(
        self, entity_id: object
    ) -> None:
        assert a_reference(entity_id=entity_id).entity_id is None

    @pytest.mark.parametrize("entity_id", [True, [], {}, 1.5])
    def test_rejects_an_identifier_that_is_not_a_key(self, entity_id: object) -> None:
        with pytest.raises(InvalidFileReferenceError):
            a_reference(entity_id=entity_id)

    def test_rejects_an_overlong_identifier(self) -> None:
        with pytest.raises(InvalidFileReferenceError):
            a_reference(entity_id="x" * 129)

    @pytest.mark.parametrize("field", ["entity_type", "context"])
    def test_requires_the_descriptive_fields(self, field: str) -> None:
        for missing in ("  ", None, 7):
            with pytest.raises(InvalidFileReferenceError):
                a_reference(**{field: missing})  # type: ignore[arg-type]

    def test_rejects_a_malformed_owner_uuid(self) -> None:
        with pytest.raises(InvalidFileReferenceError):
            a_reference(entity_uuid="not-a-uuid")

    def test_leaves_the_reference_record_key_to_the_database(self) -> None:
        assert a_reference().id is None

    def test_knows_when_two_references_describe_the_same_thing(self) -> None:
        assert a_reference().points_at(a_reference(entity_uuid=uuid4()))
        assert not a_reference().points_at(a_reference(entity_id=2))

    def test_treats_two_unidentified_references_as_the_same_thing(self) -> None:
        assert a_reference(entity_id=None).points_at(a_reference(entity_id=None))
        assert not a_reference(entity_id=None).points_at(a_reference(entity_id=1))


class TestRegister:
    def test_records_what_was_written(self) -> None:
        stored_file = a_file(size_bytes=2048)

        assert stored_file.disk == "local"
        assert stored_file.size_bytes == 2048
        assert stored_file.key == "customs/clearance-cases/commercial_invoice.pdf"

    def test_normalizes_the_disk_name(self) -> None:
        assert a_file(disk="  LOCAL ").disk == "local"

    def test_defaults_an_absent_content_type(self) -> None:
        assert a_file(content_type=None).content_type == DEFAULT_CONTENT_TYPE
        assert a_file(content_type="   ").content_type == DEFAULT_CONTENT_TYPE

    def test_starts_without_metadata_or_references(self) -> None:
        stored_file = a_file()

        assert stored_file.metadata == {}
        assert stored_file.references == []

    def test_carries_the_metadata_it_was_given(self) -> None:
        assert a_file(metadata={"issued_by": "ACME"}).metadata == {"issued_by": "ACME"}

    @pytest.mark.parametrize("size_bytes", [0, -1, "2048", 12.5, True])
    def test_refuses_an_empty_or_unmeasured_file(self, size_bytes: object) -> None:
        with pytest.raises(InvalidStoredFileError):
            a_file(size_bytes=size_bytes)  # type: ignore[arg-type]

    @pytest.mark.parametrize("metadata", [[], "{}", 7])
    def test_refuses_metadata_that_is_not_a_json_object(self, metadata: object) -> None:
        with pytest.raises(InvalidStoredFileError):
            a_file(metadata=metadata)  # type: ignore[arg-type]

    def test_refuses_an_empty_disk(self) -> None:
        with pytest.raises(InvalidStoredFileError):
            a_file(disk="   ")


class TestReferences:
    def test_attaches_the_owning_aggregate(self) -> None:
        stored_file = a_file(references=[a_reference()])

        assert stored_file.is_referenced_by("customs", "ClearanceCase", "1")

    def test_ignores_the_same_owner_declared_twice(self) -> None:
        stored_file = a_file(references=[a_reference(), a_reference()])

        assert len(stored_file.references) == 1

    def test_keeps_two_different_owners(self) -> None:
        stored_file = a_file(
            references=[a_reference(entity_id=1), a_reference(entity_id=2)]
        )

        assert len(stored_file.references) == 2

    def test_refuses_anything_that_is_not_a_reference(self) -> None:
        with pytest.raises(InvalidStoredFileError):
            a_file().relate_to("customs")  # type: ignore[arg-type]

    def test_answers_no_for_an_unrelated_entity(self) -> None:
        stored_file = a_file(references=[a_reference()])

        assert not stored_file.is_referenced_by("shipment", "Shipment", "1")

    def test_answers_the_broader_question_without_an_identifier(self) -> None:
        stored_file = a_file(references=[a_reference(entity_id=None)])

        assert stored_file.is_referenced_by("customs", "ClearanceCase")
        assert not stored_file.is_referenced_by("customs", "ClearanceCase", "1")

    def test_carries_no_references_when_the_caller_declared_none(self) -> None:
        assert a_file(references=None).references == []
