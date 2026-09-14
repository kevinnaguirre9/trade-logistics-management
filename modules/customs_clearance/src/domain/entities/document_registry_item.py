"""A legal document registered against a clearance case."""

from uuid import UUID, uuid4

from modules.customs_clearance.src.domain.enums import DocumentType
from modules.customs_clearance.src.domain.exceptions import (
    InvalidDocumentReferenceError,
)

#: Longest accepted inspector identifier.
MAX_INSPECTOR_ID_LENGTH = 128


class DocumentRegistryItem:
    """One document attached to a case, and whether an inspector cleared it.

    The document itself is not here. It lives in the Files module, and this
    entity holds its ``file_uuid`` and nothing else - no URL, no bucket, no
    storage class - so customs never learns where the bytes are kept and the
    two modules stay independent.

    Internal entity of the :class:`~modules.customs_clearance.src.domain.\
clearance_case.ClearanceCase` aggregate: it is only ever reached through its
    root.
    """

    def __init__(
        self,
        document_id: UUID,
        document_type: DocumentType,
        file_uuid: UUID,
        is_verified: bool = False,
        verified_by_inspector_id: str | None = None,
    ) -> None:
        self.id = document_id
        self.document_type = document_type
        self.file_uuid = file_uuid
        self.is_verified = is_verified
        self.verified_by_inspector_id = verified_by_inspector_id

    @classmethod
    def attach(
        cls,
        document_type: DocumentType | str,
        file_uuid: UUID | str,
    ) -> "DocumentRegistryItem":
        """Register an uploaded file as a document of the given type.

        A freshly attached document is always unverified: clearing it is an
        inspector's decision, never the caller's.
        """
        return cls(
            document_id=uuid4(),
            document_type=cls._validated_type(document_type),
            file_uuid=cls._validated_file_uuid(file_uuid),
            is_verified=False,
            verified_by_inspector_id=None,
        )

    @staticmethod
    def _validated_type(value: object) -> DocumentType:
        """Return the document type, or raise."""
        if isinstance(value, DocumentType):
            return value

        if isinstance(value, str):
            try:
                return DocumentType(value.strip().upper())
            except ValueError:
                pass

        accepted = ", ".join(member.value for member in DocumentType)
        raise InvalidDocumentReferenceError(
            f"'{value}' is not a document customs accepts; expected one of {accepted}."
        )

    @staticmethod
    def _validated_file_uuid(value: object) -> UUID:
        """Return the identifier of the stored file, or raise."""
        if isinstance(value, UUID):
            return value

        if isinstance(value, str):
            try:
                return UUID(value.strip())
            except ValueError:
                raise InvalidDocumentReferenceError(
                    f"'{value}' is not a valid file identifier."
                ) from None

        raise InvalidDocumentReferenceError("The file identifier must be a UUID.")

    def __repr__(self) -> str:
        """Return a debugging representation of the entity."""
        return (
            f"DocumentRegistryItem(id={self.id}, type={self.document_type}, "
            f"file_uuid={self.file_uuid}, is_verified={self.is_verified})"
        )
