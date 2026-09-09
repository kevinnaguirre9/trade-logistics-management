"""What a stored file is about, in another bounded context."""

from uuid import UUID

from modules.files.src.domain.exceptions import InvalidFileReferenceError

#: Longest accepted value for each descriptive field of a reference.
MAX_FIELD_LENGTH = 128


class FileReference:
    """A link from a stored file to the thing it belongs to.

    A customs document, for example, is a file referencing
    ``entity_type='ClearanceCase'`` in ``context='customs'``. The reference is
    made of plain values: the Files module never imports another module, and no
    foreign key crosses a schema, so the link is descriptive rather than
    enforced.

    Only ``context`` and ``entity_type`` are required. What they name is not
    always an aggregate with a row of its own - a reference can describe an
    external entity, or a whole kind of thing, that has files but no identifier
    here - so both identifying fields are optional:

    * ``entity_id`` - the primary key of the referenced entity, when it has
      one, as text so an integer key and a UUID key are stored the same way;
    * ``entity_uuid`` - its UUID, when the owning context has one as well.

    ``id`` is this reference row's own key, assigned by the database. Callers
    never send it; they read it back.

    Internal entity of the :class:`~modules.files.src.domain.stored_file.\
StoredFile` aggregate: it is only ever reached through its root.
    """

    def __init__(
        self,
        context: str,
        entity_type: str,
        entity_id: str | None = None,
        entity_uuid: UUID | None = None,
        reference_id: int | None = None,
    ) -> None:
        self.context = context
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.entity_uuid = entity_uuid
        # Surrogate key of the row; assigned by the database on insert.
        self.id = reference_id

    @classmethod
    def declare(
        cls,
        context: str,
        entity_type: str,
        entity_id: object = None,
        entity_uuid: UUID | str | None = None,
    ) -> "FileReference":
        """Return a validated reference to something in another context."""
        return cls(
            context=cls._validated_text(context, "context"),
            entity_type=cls._validated_text(entity_type, "entity type"),
            entity_id=cls._validated_identifier(entity_id),
            entity_uuid=cls._validated_uuid(entity_uuid),
        )

    @staticmethod
    def _validated_text(value: object, label: str) -> str:
        """Return a required descriptive field, or raise."""
        if not isinstance(value, str):
            raise InvalidFileReferenceError(f"The {label} must be a string.")

        text = value.strip()
        if not text:
            raise InvalidFileReferenceError(f"The {label} is required.")
        if len(text) > MAX_FIELD_LENGTH:
            raise InvalidFileReferenceError(
                f"The {label} is longer than {MAX_FIELD_LENGTH} characters."
            )
        return text

    @staticmethod
    def _validated_identifier(value: object) -> str | None:
        """Return the referenced key as text, ``None`` when there is none.

        Integers are accepted because plenty of contexts key their entities
        that way; they are stored as text so one column serves every kind of
        key.
        """
        if value is None:
            return None
        if isinstance(value, bool):
            raise InvalidFileReferenceError(
                "The entity identifier must be a string, an integer or a UUID."
            )
        if isinstance(value, int | UUID):
            return str(value)
        if not isinstance(value, str):
            raise InvalidFileReferenceError(
                "The entity identifier must be a string, an integer or a UUID."
            )

        identifier = value.strip()
        if not identifier:
            return None
        if len(identifier) > MAX_FIELD_LENGTH:
            raise InvalidFileReferenceError(
                f"The entity identifier is longer than {MAX_FIELD_LENGTH} characters."
            )
        return identifier

    @staticmethod
    def _validated_uuid(value: UUID | str | None) -> UUID | None:
        """Return the referenced entity's UUID, when it has one."""
        if value is None:
            return None
        if isinstance(value, UUID):
            return value
        if isinstance(value, str):
            candidate = value.strip()
            if not candidate:
                return None
            try:
                return UUID(candidate)
            except ValueError:
                raise InvalidFileReferenceError(
                    f"'{value}' is not a valid entity UUID."
                ) from None

        raise InvalidFileReferenceError("The entity UUID must be a UUID.")

    def points_at(self, other: "FileReference") -> bool:
        """Return ``True`` when both describe the same thing.

        Two references with no ``entity_id`` and the same context and type
        describe the same thing, so declaring that twice is still a repeat.
        """
        return (
            isinstance(other, FileReference)
            and other.context == self.context
            and other.entity_type == self.entity_type
            and other.entity_id == self.entity_id
        )

    def __repr__(self) -> str:
        """Return a debugging representation of the reference."""
        return (
            f"FileReference(context={self.context}, "
            f"entity_type={self.entity_type}, entity_id={self.entity_id})"
        )
