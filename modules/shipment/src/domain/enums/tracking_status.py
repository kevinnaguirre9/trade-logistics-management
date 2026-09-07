"""Lifecycle status of a shipment."""

from enum import StrEnum


class TrackingStatus(StrEnum):
    """Every state a shipment can be in.

    The stored representation is the member value (``"Draft"``), which is what
    the database CHECK constraint and the public API contract expose.
    """

    DRAFT = "Draft"
    READY_FOR_MANIFEST = "ReadyForManifest"
    AWAITING_CUSTOMS_RELEASE = "AwaitingCustomsRelease"
    IN_TRANSIT = "InTransit"
    DELIVERED = "Delivered"
    EXCEPTION_HELD = "ExceptionHeld"
