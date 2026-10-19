"""Browser origin handling for local frontend ports and session cookies."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.mark.asyncio
@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://localhost:3001"])
async def test_allowed_origin_session_lifecycle(
    origin, test_settings, test_session_factory, monkeypatch
):
    test_settings.frontend_origin = "http://localhost:3000, http://localhost:3001"
    monkeypatch.setattr("app.main.get_settings", lambda: test_settings)
    app = create_app()
    app.state.settings = test_settings
    app.state.session_factory = test_session_factory
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost:8000"
    ) as client:
        preflight = await client.options(
            "/api/session",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == origin
        assert preflight.headers["access-control-allow-credentials"] == "true"

        # A missing session should be readable by the browser, not a network error.
        missing = await client.get("/api/session", headers={"Origin": origin})
        assert missing.status_code == 401
        assert missing.headers["access-control-allow-origin"] == origin

        created = await client.post(
            "/api/session", json={"nickname": "Test"}, headers={"Origin": origin}
        )
        assert created.status_code == 200
        assert "eb_session" in client.cookies
        deleted = await client.delete("/api/session", headers={"Origin": origin})
        assert deleted.status_code == 200


@pytest.mark.asyncio
async def test_unlisted_origin_is_rejected(test_settings, test_session_factory, monkeypatch):
    test_settings.app_env = type(test_settings.app_env).DEVELOPMENT
    monkeypatch.setattr("app.main.get_settings", lambda: test_settings)
    app = create_app()
    app.state.settings = test_settings
    app.state.session_factory = test_session_factory
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost:8000"
    ) as client:
        headers = {"Origin": "https://untrusted.example"}
        preflight = await client.options(
            "/api/session",
            headers={**headers, "Access-Control-Request-Method": "POST"},
        )
        assert preflight.status_code == 400
        assert "access-control-allow-origin" not in preflight.headers
        response = await client.post("/api/session", json={}, headers=headers)
        assert response.status_code == 403
        assert "access-control-allow-origin" not in response.headers
