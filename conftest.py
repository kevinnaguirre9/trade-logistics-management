"""Pytest fixtures shared by every module test suite."""

from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from main import create_app


@pytest.fixture(scope="session")
def app() -> FastAPI:
    """Build the application once per test session."""
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Return an HTTP client bound to the ASGI app (no network involved)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http
