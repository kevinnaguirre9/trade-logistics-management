"""The Customs Clearance module exposes a router and maps its objects once."""

from fastapi import APIRouter

from modules.customs_clearance.src.api import router
from modules.customs_clearance.src.infrastructure.database import SCHEMA
from modules.customs_clearance.src.infrastructure.database.entities import (
    start_mappers,
)


def test_module_publishes_a_router() -> None:
    assert isinstance(router, APIRouter)


def test_module_owns_its_own_schema() -> None:
    assert SCHEMA == "customs"


def test_start_mappers_is_idempotent() -> None:
    start_mappers()
    start_mappers()
