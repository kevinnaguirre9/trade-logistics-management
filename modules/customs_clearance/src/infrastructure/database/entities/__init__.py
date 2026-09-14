"""Table definitions and imperative mappings of the Customs Clearance module.

Tables are declared against the shared metadata using the module schema, and
domain objects are attached to them with
``mapper_registry.map_imperatively(...)`` inside :func:`start_mappers`.
"""

from sqlalchemy.orm import composite, relationship

from modules.customs_clearance.src.domain.clearance_case import ClearanceCase
from modules.customs_clearance.src.domain.entities import DocumentRegistryItem
from modules.customs_clearance.src.domain.value_objects import CaseId, Money
from modules.customs_clearance.src.infrastructure.database.entities.clearance_case_document_table import (  # noqa: E501
    clearance_case_documents_table,
    document_type_type,
)
from modules.customs_clearance.src.infrastructure.database.entities.clearance_case_table import (  # noqa: E501
    assessment_status_type,
    clearance_cases_table,
)
from modules.shared.database import mapper_registry

_mappers_started = False


def start_mappers() -> None:
    """Attach the Customs Clearance domain objects to their tables (idempotent).

    Called once by the application composition root at start-up.

    Each value object is mapped as a composite over the columns it owns. The
    underlying columns are also mapped, under ``_``-prefixed names, so a
    composite can carry the same name as the column it is built from.
    """
    global _mappers_started
    if _mappers_started:
        return

    columns = clearance_cases_table.c

    mapper_registry.map_imperatively(
        DocumentRegistryItem,
        clearance_case_documents_table,
        exclude_properties=["created_at", "updated_at"],
    )

    mapper_registry.map_imperatively(
        ClearanceCase,
        clearance_cases_table,
        properties={
            "_id": columns.id,
            "id": composite(CaseId, columns.id),
            # Money is nullable until it is known, so it is rebuilt through a
            # factory that answers None for an all-NULL row.
            "_declaration_amount": columns.declaration_amount,
            "_declaration_currency": columns.declaration_currency,
            "declaration_value": composite(
                Money.from_columns,
                columns.declaration_amount,
                columns.declaration_currency,
            ),
            "_duty_amount": columns.duty_amount,
            "_duty_currency": columns.duty_currency,
            "duty_fee": composite(
                Money.from_columns,
                columns.duty_amount,
                columns.duty_currency,
            ),
            # The documents are part of the aggregate: they cascade with their
            # root and load eagerly, because a lazy load under asyncio would
            # raise the moment a caller touched the collection outside the
            # awaited query.
            "documents": relationship(
                DocumentRegistryItem,
                cascade="all, delete-orphan",
                lazy="selectin",
                passive_deletes=True,
                order_by=clearance_case_documents_table.c.created_at,
            ),
        },
        exclude_properties=["created_at", "updated_at"],
    )

    _mappers_started = True


__all__ = [
    "assessment_status_type",
    "clearance_case_documents_table",
    "clearance_cases_table",
    "document_type_type",
    "start_mappers",
]
