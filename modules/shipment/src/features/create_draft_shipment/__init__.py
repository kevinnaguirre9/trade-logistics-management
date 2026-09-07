"""Vertical slice: create draft shipment (controller + command + handler).

Re-exported here so callers outside the slice (the module router, the tests)
depend on the slice, not on its internal file layout.
"""

from modules.shipment.src.features.create_draft_shipment.create_draft_shipment_command import (  # noqa: E501
    CreateDraftShipmentCommand,
)
from modules.shipment.src.features.create_draft_shipment.create_draft_shipment_controller import (  # noqa: E501
    CreateDraftShipmentResponse,
    get_create_draft_shipment_handler,
    router,
)
from modules.shipment.src.features.create_draft_shipment.create_draft_shipment_handler import (  # noqa: E501
    CreateDraftShipmentHandler,
)

__all__ = [
    "CreateDraftShipmentCommand",
    "CreateDraftShipmentHandler",
    "CreateDraftShipmentResponse",
    "get_create_draft_shipment_handler",
    "router",
]
