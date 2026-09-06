"""The Shipment module exposes a router and configures its mappings once."""

from fastapi import APIRouter

from modules.shipment.src.api import router
from modules.shipment.src.infrastructure.database import SCHEMA
from modules.shipment.src.infrastructure.database.entities import start_mappers


def test_module_publishes_a_router() -> None:
    assert isinstance(router, APIRouter)


def test_module_owns_its_own_schema() -> None:
    assert SCHEMA == "shipment"


def test_start_mappers_is_idempotent() -> None:
    start_mappers()
    start_mappers()
