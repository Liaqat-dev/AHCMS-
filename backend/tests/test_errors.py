"""Error-path tests: unhandled 500s, header preservation, CORS on errors."""

from __future__ import annotations

from app.exceptions.errors import RateLimited
from app.main import app
from fastapi import HTTPException


@app.get("/_test/boom", include_in_schema=False)
async def _boom() -> None:
    raise RuntimeError("kaboom")


@app.get("/_test/unauthorized", include_in_schema=False)
async def _unauthorized() -> None:
    raise HTTPException(
        status_code=401,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.get("/_test/rate-limited", include_in_schema=False)
async def _rate_limited() -> None:
    raise RateLimited(headers={"Retry-After": "30"})


async def test_unhandled_500_keeps_envelope_and_request_id(client):
    resp = await client.get("/_test/boom", headers={"X-Request-ID": "rid-500-test"})
    assert resp.status_code == 500
    error = resp.json()["error"]
    assert error["code"] == "internal_error"
    assert error["message"] == "Internal server error"
    # The correlation id must survive onto the 500 envelope and header.
    assert error["request_id"] == "rid-500-test"
    assert resp.headers.get("X-Request-ID") == "rid-500-test"


async def test_unhandled_500_has_cors_headers(client):
    resp = await client.get(
        "/_test/boom", headers={"Origin": "http://localhost:4200"}
    )
    assert resp.status_code == 500
    assert resp.headers.get("Access-Control-Allow-Origin") == "http://localhost:4200"


async def test_http_exception_headers_preserved(client):
    resp = await client.get("/_test/unauthorized")
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"
    error = resp.json()["error"]
    assert error["code"] == "http_401"
    assert error["message"] == "Authentication required"


async def test_app_error_headers_preserved(client):
    resp = await client.get("/_test/rate-limited")
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") == "30"
    assert resp.json()["error"]["code"] == "rate_limited"


async def test_validation_details_do_not_echo_input(client):
    # A login body is the case that matters: the rejected payload carries a
    # password, which must never come back in the error details.
    # Too short for the field, and a distinctive value that cannot collide
    # with any word pydantic puts in the error type or message.
    secret = "zxq9"
    resp = await client.post(
        "/api/v1/auth/student/login", json={"roll_no": "R-1", "password": secret}
    )
    assert resp.status_code == 422
    details = resp.json()["error"]["details"]
    assert details, "expected at least one validation error"
    for item in details:
        assert set(item) == {"loc", "msg", "type"}
    assert secret not in resp.text
