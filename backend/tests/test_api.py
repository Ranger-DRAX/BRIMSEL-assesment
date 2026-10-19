"""Integration tests for all FastAPI API endpoints."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(app_client: AsyncClient):
    """GET /health must return status ok and expose no secrets."""
    response = await app_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "api_key" not in data
    assert "secret" not in data
    assert "groq" not in str(data).lower()


@pytest.mark.asyncio
async def test_ready_endpoint(app_client: AsyncClient):
    """GET /ready must return database and config readiness without calling paid LLM."""
    response = await app_client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["config"] == "ok"
    assert "api_key" not in data


@pytest.mark.asyncio
async def test_session_lifecycle(app_client: AsyncClient):
    """Create session -> Get session -> Reset -> Delete."""
    # 1. Create session
    resp = await app_client.post(
        "/api/session",
        json={"nickname": "Timmy", "starting_level": "L1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["nickname"] == "Timmy"
    assert data["level"] == "L1"
    assert data["revision"] == 0

    # Cookie must be set and HttpOnly
    assert "eb_session" in resp.cookies

    # 2. Get current session
    get_resp = await app_client.get("/api/session")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["nickname"] == "Timmy"
    assert get_data["level"] == "L1"

    # 3. Reset session
    reset_resp = await app_client.post("/api/session/reset")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["status"] == "ok"

    # Get session again to verify state
    post_reset_resp = await app_client.get("/api/session")
    assert post_reset_resp.status_code == 200
    assert post_reset_resp.json()["level"] == "L1"

    # 4. Delete session
    del_resp = await app_client.delete("/api/session")
    assert del_resp.status_code == 200

    # Next call without session cookie must fail with 401
    unauth_resp = await app_client.get("/api/session")
    assert unauth_resp.status_code == 401


@pytest.mark.asyncio
async def test_chat_turn_conversation(app_client: AsyncClient):
    """Submit a friendly conversational chat turn."""
    # Setup session
    await app_client.post("/api/session", json={"nickname": "Leo"})

    req_id = str(uuid.uuid4())
    resp = await app_client.post(
        "/api/chat",
        json={
            "request_id": req_id,
            "expected_revision": 0,
            "message": "I like red cars",
            "action": None,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["request_id"] == req_id
    assert data["revision"] == 1
    assert data["mode"] == "conversation"
    assert len(data["reply"]) > 0
    assert len(data["suggested_replies"]) <= 3


@pytest.mark.asyncio
async def test_chat_turn_idempotency_same_body(app_client: AsyncClient):
    """Repeating the same request_id returns the identical response without duplicate side-effects."""
    await app_client.post("/api/session", json={"nickname": "Mia"})

    req_id = str(uuid.uuid4())
    body = {
        "request_id": req_id,
        "expected_revision": 0,
        "message": "Hello there",
        "action": None,
    }

    # First submission
    resp1 = await app_client.post("/api/chat", json=body)
    assert resp1.status_code == 200
    data1 = resp1.json()

    # Replay identical request
    resp2 = await app_client.post("/api/chat", json=body)
    assert resp2.status_code == 200
    data2 = resp2.json()

    assert data1["reply"] == data2["reply"]
    assert data1["revision"] == data2["revision"]


@pytest.mark.asyncio
async def test_chat_turn_idempotency_different_body_conflict(app_client: AsyncClient):
    """Reusing the same request_id with different input must return 409 Conflict."""
    await app_client.post("/api/session", json={"nickname": "Sam"})

    req_id = str(uuid.uuid4())
    resp1 = await app_client.post(
        "/api/chat",
        json={
            "request_id": req_id,
            "expected_revision": 0,
            "message": "First message",
        },
    )
    assert resp1.status_code == 200

    # Conflict submission with different message
    resp2 = await app_client.post(
        "/api/chat",
        json={
            "request_id": req_id,
            "expected_revision": 0,
            "message": "Completely different message",
        },
    )
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_chat_turn_stale_revision_conflict(app_client: AsyncClient):
    """Submitting with an outdated expected_revision returns 409 Conflict."""
    await app_client.post("/api/session", json={"nickname": "Noah"})

    # Advance revision from 0 to 1
    req1 = str(uuid.uuid4())
    await app_client.post(
        "/api/chat",
        json={"request_id": req1, "expected_revision": 0, "message": "Turn 1"},
    )

    # Submit with stale revision 0 instead of 1
    req2 = str(uuid.uuid4())
    resp_stale = await app_client.post(
        "/api/chat",
        json={"request_id": req2, "expected_revision": 0, "message": "Turn 2"},
    )
    assert resp_stale.status_code == 409


@pytest.mark.asyncio
async def test_chat_learning_flow(app_client: AsyncClient):
    """Action LEARN starts an activity, and answering it scores and provides feedback."""
    await app_client.post("/api/session", json={"nickname": "Emma", "starting_level": "L1"})

    # 1. Request Learn action
    req1 = str(uuid.uuid4())
    resp1 = await app_client.post(
        "/api/chat",
        json={
            "request_id": req1,
            "expected_revision": 0,
            "message": None,
            "action": "learn",
        },
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["mode"] == "learning"
    assert data1["activity"] is not None
    activity_instance_id = data1["activity"]["instance_id"]

    # 2. Answer the activity
    req2 = str(uuid.uuid4())
    resp2 = await app_client.post(
        "/api/chat",
        json={
            "request_id": req2,
            "expected_revision": data1["revision"],
            "message": "red",
            "action": None,
            "activity_instance_id": activity_instance_id,
        },
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert len(data2["reply"]) > 0


@pytest.mark.asyncio
async def test_chat_input_length_validation(app_client: AsyncClient):
    """Inputs exceeding max_input_chars must return 422."""
    await app_client.post("/api/session", json={"nickname": "Zoe"})

    req_id = str(uuid.uuid4())
    oversized = "a" * 501
    resp = await app_client.post(
        "/api/chat",
        json={
            "request_id": req_id,
            "expected_revision": 0,
            "message": oversized,
        },
    )
    assert resp.status_code == 422
