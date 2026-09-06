"""Composition-root smoke tests: the monolith boots and reports errors as RFC 9457."""

from httpx import AsyncClient

from modules.shared.http.exceptions.problem_details import PROBLEM_CONTENT_TYPE


async def test_health_endpoint_reports_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_unknown_route_returns_problem_details(client: AsyncClient) -> None:
    response = await client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)

    problem = response.json()
    assert problem["status"] == 404
    assert problem["instance"] == "/does-not-exist"
    assert problem["type"].endswith("/not-found")
