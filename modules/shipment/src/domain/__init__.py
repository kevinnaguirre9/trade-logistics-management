"""Domain layer of the Shipment module: aggregates, entities and value objects.

Pure Python only: no SQLAlchemy, FastAPI or Pydantic imports are allowed here.
Persistence is attached from the infrastructure layer through imperative
mapping.
"""

from modules.shipment.src.domain.shipment import Shipment
from modules.shipment.src.domain.waybill_number_generator import (
    WaybillNumberGenerator,
)

__all__ = ["Shipment", "WaybillNumberGenerator"]
