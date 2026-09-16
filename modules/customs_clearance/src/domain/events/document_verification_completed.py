"""Published once every document customs requires has been verified."""

from dataclasses import dataclass

from modules.shared.message_bus import IntegrationMessage


@dataclass(frozen=True, slots=True)
class DocumentVerificationCompleted(IntegrationMessage):
    """The paperwork is complete and the case is ready to be risk assessed.

    This is both the domain event and the contract that leaves the module:
    ``IntegrationMessage`` is a plain frozen dataclass, so the domain keeps its
    framework independence and there is no second class to keep in step.

    It is a fact, not an instruction. Customs announces that verification
    finished; the risk assessment slice decides to act on it, which leaves room
    for anything else that eventually cares.

    The payload stays thin: the risk assessment loads the case it names and
    reads whatever else it needs from it.
    """

    case_id: str
    shipment_id: str
