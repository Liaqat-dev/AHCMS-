"""Auth flow tests: login, refresh rotation + reuse detection, logout, cap."""

from __future__ import annotations

import jwt
from app.core.config import settings

LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
COOKIE = settings.REFRESH_COOKIE_NAME


def _decode(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


async def _login(db_client, email="alice@test.edu", password="password123"):
    return await db_client.post(LOGIN, json={"email": email, "password": password})


def _use_cookie(db_client, value: str | None) -> None:
    db_client.cookies.clear()
    if value is not None:
        db_client.cookies.set(COOKIE, value)


async def test_login_success(db_client, make_user):
    await make_user("alice@test.edu", roles=["teacher"])
    resp = await _login(db_client)
    assert resp.status_code == 200
    body = resp.json()

    claims = _decode(body["access_token"])
    assert claims["type"] == "access"
    assert claims["roles"] == ["teacher"]
    assert "courses:read" in claims["perms"]
    assert body["user"]["email"] == "alice@test.edu"
    assert body["user"]["roles"] == ["teacher"]

    set_cookie = resp.headers["set-cookie"]
    assert COOKIE in set_cookie
    assert "HttpOnly" in set_cookie
    assert f"Path={settings.REFRESH_COOKIE_PATH}" in set_cookie


async def test_login_wrong_password_is_generic(db_client, make_user):
    await make_user("alice@test.edu", roles=["teacher"])
    resp = await _login(db_client, password="wrong-password")
    assert resp.status_code == 401
    assert resp.json()["error"]["message"] == "Invalid email or password"
    # Unknown email → identical message (no user enumeration).
    resp2 = await _login(db_client, email="ghost@test.edu")
    assert resp2.json()["error"]["message"] == resp.json()["error"]["message"]


async def test_login_inactive_user(db_client, make_user):
    await make_user("gone@test.edu", roles=["teacher"], is_active=False)
    resp = await _login(db_client, email="gone@test.edu")
    assert resp.status_code == 401


async def test_refresh_rotates_and_detects_reuse(db_client, make_user):
    await make_user("alice@test.edu", roles=["teacher"])
    login_resp = await _login(db_client)
    old_cookie = login_resp.cookies[COOKIE]

    _use_cookie(db_client, old_cookie)
    refresh_resp = await db_client.post(REFRESH)
    assert refresh_resp.status_code == 200
    new_cookie = refresh_resp.cookies[COOKIE]
    assert new_cookie != old_cookie

    # Replaying the pre-rotation cookie = reuse → 401 and the session dies.
    _use_cookie(db_client, old_cookie)
    reuse_resp = await db_client.post(REFRESH)
    assert reuse_resp.status_code == 401

    # The legitimate (rotated) cookie is now dead too — whole session revoked.
    _use_cookie(db_client, new_cookie)
    after_resp = await db_client.post(REFRESH)
    assert after_resp.status_code == 401


async def test_refresh_without_cookie(db_client):
    _use_cookie(db_client, None)
    resp = await db_client.post(REFRESH)
    assert resp.status_code == 401


async def test_logout_revokes_session(db_client, make_user):
    await make_user("alice@test.edu", roles=["teacher"])
    login_resp = await _login(db_client)
    cookie = login_resp.cookies[COOKIE]

    _use_cookie(db_client, cookie)
    logout_resp = await db_client.post(LOGOUT)
    assert logout_resp.status_code == 204

    _use_cookie(db_client, cookie)
    resp = await db_client.post(REFRESH)
    assert resp.status_code == 401


async def test_session_cap_evicts_oldest(db_client, make_user):
    await make_user("alice@test.edu", roles=["teacher"])
    cookies = []
    for _ in range(settings.MAX_SESSIONS_PER_USER + 1):
        _use_cookie(db_client, None)
        resp = await _login(db_client)
        assert resp.status_code == 200
        cookies.append(resp.cookies[COOKIE])

    # First (oldest) session was evicted by the 6th login...
    _use_cookie(db_client, cookies[0])
    assert (await db_client.post(REFRESH)).status_code == 401
    # ...while the second is still alive.
    _use_cookie(db_client, cookies[1])
    assert (await db_client.post(REFRESH)).status_code == 200


async def test_me_and_sessions(db_client, make_user):
    await make_user("alice@test.edu", roles=["teacher"])
    login_resp = await _login(db_client)
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = await db_client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["roles"] == ["teacher"]

    sessions = await db_client.get("/api/v1/auth/sessions", headers=headers)
    assert sessions.status_code == 200
    items = sessions.json()
    assert len(items) == 1
    assert items[0]["current"] is True


async def test_me_requires_token(db_client):
    resp = await db_client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"

    resp = await db_client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert resp.status_code == 401
