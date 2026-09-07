"""PostgreSQL implementations of the Shipment repository interfaces."""

from modules.shipment.src.infrastructure.repositories.postgres_shipment_repository import (  # noqa: E501
    PostgresShipmentRepository,
)

__all__ = ["PostgresShipmentRepository"]
