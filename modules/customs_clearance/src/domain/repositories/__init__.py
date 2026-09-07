"""Repository interfaces of the Customs Clearance module.

Declared in the domain and implemented in the infrastructure layer, so the
dependency points inwards.
"""

from modules.customs_clearance.src.domain.repositories.clearance_case_repository import (  # noqa: E501
    ClearanceCaseRepository,
)

__all__ = ["ClearanceCaseRepository"]
