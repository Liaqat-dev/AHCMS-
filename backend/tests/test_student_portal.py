"""Student portal tests.

A student is not a ``User``: they sign in with a roll number, hold no roles or
permissions, and can reach nothing but their own profile.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import settings
from app.db import models
from sqlalchemy.exc import IntegrityError

STUDENT_LOGIN = "/api/v1/auth/student/login"
STUDENT_REFRESH = "/api/v1/auth/student/refresh"
STUDENT_LOGOUT = "/api/v1/auth/student/logout"
STUDENT_ME = "/api/v1/student/me"
STAFF_LOGIN = "/api/v1/auth/login"
STAFF_REFRESH = "/api/v1/auth/refresh"
# Staff and students carry separate refresh cookies; see settings.
REFRESH_COOKIE = settings.REFRESH_COOKIE_NAME
STUDENT_COOKIE = settings.STUDENT_REFRESH_COOKIE_NAME


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _student_token(db_client, roll_no: str, password: str = "password123") -> str:
    resp = await db_client.post(
        STUDENT_LOGIN, json={"roll_no": roll_no, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _staff_token(db_client, email: str, password: str = "password123") -> str:
    resp = await db_client.post(STAFF_LOGIN, json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ----- Login -----------------------------------------------------------------


async def test_student_logs_in_with_roll_no(db_client, make_student):
    await make_student("BSCS-2024-001", full_name="Ada Lovelace")

    resp = await db_client.post(
        STUDENT_LOGIN, json={"roll_no": "BSCS-2024-001", "password": "password123"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["student"]["roll_no"] == "BSCS-2024-001"
    assert body["student"]["full_name"] == "Ada Lovelace"
    # A student principal carries no roles and no permissions at all.
    assert "roles" not in body["student"]
    assert "permissions" not in body["student"]
    assert STUDENT_COOKIE in resp.cookies


async def test_student_login_wrong_password_is_generic(db_client, make_student):
    await make_student("BSCS-2024-001")
    resp = await db_client.post(
        STUDENT_LOGIN, json={"roll_no": "BSCS-2024-001", "password": "wrong-password"}
    )
    assert resp.status_code == 401
    # Same message as an unknown roll number, so enumeration gains nothing.
    unknown = await db_client.post(
        STUDENT_LOGIN, json={"roll_no": "NO-SUCH-ROLL", "password": "wrong-password"}
    )
    assert unknown.status_code == 401
    assert resp.json()["error"]["message"] == unknown.json()["error"]["message"]


async def test_student_without_password_cannot_log_in(db_client, make_student):
    """A record created before credentials are issued must not be loginable."""
    await make_student("BSCS-2024-002", password=None)
    resp = await db_client.post(
        STUDENT_LOGIN, json={"roll_no": "BSCS-2024-002", "password": "password123"}
    )
    assert resp.status_code == 401


async def test_inactive_student_cannot_log_in(db_client, make_student):
    await make_student("BSCS-2024-003", is_active=False)
    resp = await db_client.post(
        STUDENT_LOGIN, json={"roll_no": "BSCS-2024-003", "password": "password123"}
    )
    assert resp.status_code == 401


async def test_email_is_not_accepted_as_a_student_login(db_client, make_student):
    await make_student("BSCS-2024-001")
    resp = await db_client.post(
        STUDENT_LOGIN, json={"email": "a@b.edu", "password": "password123"}
    )
    assert resp.status_code == 422


# ----- The portal ------------------------------------------------------------


async def test_student_reads_own_profile(db_client, make_student):
    await make_student("BSCS-2024-001", full_name="Ada Lovelace")
    token = await _student_token(db_client, "BSCS-2024-001")

    resp = await db_client.get(STUDENT_ME, headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["roll_no"] == "BSCS-2024-001"


async def test_portal_requires_a_token(db_client):
    assert (await db_client.get(STUDENT_ME)).status_code == 401


# ----- The two principals stay apart -----------------------------------------


async def test_student_token_is_refused_by_staff_routes(db_client, make_student):
    """The whole point: a student credential unlocks nothing but the portal."""
    await make_student("BSCS-2024-001")
    token = await _student_token(db_client, "BSCS-2024-001")

    for path in ("/api/v1/users", "/api/v1/students", "/api/v1/roles"):
        resp = await db_client.get(path, headers=_auth(token))
        assert resp.status_code == 403, f"{path} -> {resp.status_code}"
        assert resp.json()["error"]["code"] == "forbidden"

    # ...including the staff identity endpoint.
    assert (await db_client.get("/api/v1/auth/me", headers=_auth(token))).status_code == 403


async def test_staff_token_is_refused_by_the_portal(db_client, make_user):
    await make_user("root@test.edu", roles=["super_admin"])
    token = await _staff_token(db_client, "root@test.edu")

    resp = await db_client.get(STUDENT_ME, headers=_auth(token))
    assert resp.status_code == 403


async def test_staff_cookie_cannot_refresh_at_the_student_endpoint(db_client, make_user):
    await make_user("root@test.edu", roles=["super_admin"])
    login = await db_client.post(
        STAFF_LOGIN, json={"email": "root@test.edu", "password": "password123"}
    )
    staff_cookie = login.cookies[REFRESH_COOKIE]

    # Present a genuine *staff* refresh token under the student cookie name.
    # The name/path split alone would already have withheld it, so plant it
    # explicitly to prove rotate_session(expect="student") is the real guard.
    db_client.cookies.set(STUDENT_COOKIE, staff_cookie)
    resp = await db_client.post(STUDENT_REFRESH)
    assert resp.status_code == 401


async def test_student_and_staff_sessions_coexist_in_one_browser(
    db_client, make_user, make_student
):
    """The two logins must not overwrite each other's refresh cookie.

    They share an origin in development (both dev servers proxy to the same
    API), so distinct cookie names are what keeps the sessions independent.
    """
    await make_user("root@test.edu", roles=["super_admin"])
    await make_student("BSCS-2024-001")

    await db_client.post(STAFF_LOGIN, json={"email": "root@test.edu", "password": "password123"})
    await db_client.post(
        STUDENT_LOGIN, json={"roll_no": "BSCS-2024-001", "password": "password123"}
    )

    # Both cookies are live in the same jar, and each endpoint refreshes its own.
    staff_refresh = await db_client.post(STAFF_REFRESH)
    assert staff_refresh.status_code == 200, staff_refresh.text
    assert staff_refresh.json()["user"]["email"] == "root@test.edu"

    student_refresh = await db_client.post(STUDENT_REFRESH)
    assert student_refresh.status_code == 200, student_refresh.text
    assert student_refresh.json()["student"]["roll_no"] == "BSCS-2024-001"


# ----- Sessions --------------------------------------------------------------


async def test_student_refresh_rotates_the_cookie(db_client, make_student):
    await make_student("BSCS-2024-001")
    login = await db_client.post(
        STUDENT_LOGIN, json={"roll_no": "BSCS-2024-001", "password": "password123"}
    )
    first_cookie = login.cookies[STUDENT_COOKIE]

    refreshed = await db_client.post(STUDENT_REFRESH)
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.cookies[STUDENT_COOKIE] != first_cookie
    assert refreshed.json()["student"]["roll_no"] == "BSCS-2024-001"


async def test_student_logout_revokes_the_session(db_client, make_student):
    await make_student("BSCS-2024-001")
    await db_client.post(
        STUDENT_LOGIN, json={"roll_no": "BSCS-2024-001", "password": "password123"}
    )

    assert (await db_client.post(STUDENT_LOGOUT)).status_code == 204
    assert (await db_client.post(STUDENT_REFRESH)).status_code == 401


async def test_password_reset_revokes_existing_sessions(db_client, make_user, make_student):
    """A reset must lock out whoever was signed in with the old password."""
    await make_user("root@test.edu", roles=["super_admin"])
    await make_student("BSCS-2024-001")
    staff = await _staff_token(db_client, "root@test.edu")

    await db_client.post(
        STUDENT_LOGIN, json={"roll_no": "BSCS-2024-001", "password": "password123"}
    )

    listed = await db_client.get("/api/v1/students", headers=_auth(staff))
    student_id = listed.json()["items"][0]["id"]

    reset = await db_client.put(
        f"/api/v1/students/{student_id}/password",
        headers=_auth(staff),
        json={"password": "brand-new-password"},
    )
    assert reset.status_code == 200

    # The old session is dead...
    assert (await db_client.post(STUDENT_REFRESH)).status_code == 401
    # ...and only the new password works.
    assert (
        await db_client.post(
            STUDENT_LOGIN, json={"roll_no": "BSCS-2024-001", "password": "password123"}
        )
    ).status_code == 401
    await _student_token(db_client, "BSCS-2024-001", "brand-new-password")


async def test_a_session_belongs_to_exactly_one_subject(db_sessionmaker):
    """The DB itself refuses a session that is neither, or both."""
    expires = datetime.now(UTC) + timedelta(days=1)

    async with db_sessionmaker() as db:
        batch = models.AcademicSession(start_year=2024)
        db.add(batch)
        await db.flush()
        student = models.Student(
            roll_no="2024-001",
            session_id=batch.id,
            first_name="Ada",
            last_name="Lovelace",
        )
        user = models.User(email="root@test.edu", hashed_password="x")
        db.add_all([student, user])
        await db.commit()
        student_id, user_id = student.id, user.id

    async def insert(**subject) -> None:
        async with db_sessionmaker() as db:
            db.add(
                models.RefreshSession(
                    token_hash="h", jti=uuid.uuid4().hex, expires_at=expires, **subject
                )
            )
            await db.commit()

    with pytest.raises(IntegrityError):
        await insert(user_id=None, student_id=None)
    with pytest.raises(IntegrityError):
        await insert(user_id=user_id, student_id=student_id)

    # Either one alone is fine.
    await insert(student_id=student_id)
    await insert(user_id=user_id)
