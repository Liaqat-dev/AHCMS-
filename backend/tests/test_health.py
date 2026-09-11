"""Smoke tests: health endpoints + the shared error envelope."""

from __future__ import annotations


async def test_health_liveness(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body
    # Correlation id is echoed on every response.
    assert resp.headers.get("X-Request-ID")


async def test_health_db(client):
    resp = await client.get("/api/v1/health/db")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "ok"}


async def test_validation_error_envelope(client):
    # Missing `password` → 422 in the standard envelope.
    resp = await client.post("/api/v1/auth/student/login", json={"roll_no": "R-1"})
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "validation_error"
    assert error["request_id"]
    assert isinstance(error["details"], list)
    # Sanitized: submitted values must never be echoed back.
    assert all("input" not in item for item in error["details"])


async def test_not_found_envelope(client):
    resp = await client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    error = resp.json()["error"]
    assert error["code"] == "http_404"
    assert error["request_id"]


async def test_students_listing_requires_authentication(client):
    resp = await client.get("/api/v1/students")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"
