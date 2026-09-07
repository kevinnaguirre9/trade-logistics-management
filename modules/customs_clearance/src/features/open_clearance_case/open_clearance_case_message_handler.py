"""Message handler of the *open clearance case* slice.

Consumes ``ShipmentManifestFinalized``. This is the message-driven counterpart
of an HTTP controller: it turns a delivery into a command, exactly as a
controller turns a request into one.
"""

import logging

from modules.customs_clearance.src.features.open_clearance_case.open_clearance_case_command import (  # noqa: E501
    OpenClearanceCaseCommand,
)
from modules.customs_clearance.src.features.open_clearance_case.open_clearance_case_handler import (  # noqa: E501
    OpenClearanceCaseHandler,
)
from modules.customs_clearance.src.infrastructure.repositories import (
    PostgresClearanceCaseRepository,
)
from modules.shared.message_bus import MessageEnvelope, MessageHandler

logger = logging.getLogger(__name__)

#: The message this slice subscribes to. Held as a string rather than imported
#: from the shipment module: the contract crosses the boundary, the code does
#: not.
SHIPMENT_MANIFEST_FINALIZED = "ShipmentManifestFinalized"


class OpenClearanceCaseMessageHandler(MessageHandler):
    """Opens a clearance case when a shipment declares its cargo.

    The session comes from the message bus, which also writes the inbox row, so
    the new case and the record that this message was handled commit together.
    Redeliveries never reach :meth:`handle` twice.
    """

    message_type = SHIPMENT_MANIFEST_FINALIZED

    async def handle(self, envelope: MessageEnvelope) -> None:
        """Turn the delivered message into a command and run it."""
        command = OpenClearanceCaseCommand(**envelope.body)

        handler = OpenClearanceCaseHandler(
            clearance_cases=PostgresClearanceCaseRepository(self._session)
        )
        clearance_case = await handler.handle(command)

        logger.info(
            "Opened clearance case %s for shipment %s.",
            clearance_case.id,
            clearance_case.shipment_id,
        )
