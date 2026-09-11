"""Staff-facing student management (students:read / students:write)."""

from __future__ import annotations

STUDENTS = "/api/v1/students"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _staff_token(db_client, email: str, password: str = "password123") -> str:
    resp = await db_client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def test_create_read_update_student(db_client, make_user, make_session):
    await make_user("root@test.edu", roles=["super_admin"])
    token = await _staff_token(db_client, "root@test.edu")
    session_id = await make_session(2024)

    created = await db_client.post(
        STUDENTS,
        headers=_auth(token),
        json={
            "session_id": session_id,
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@test.edu",
            "password": "password123",
            "b_form_cnic": "42101-1234567-1",
        },
    )
    assert created.status_code == 201, created.text
    student = created.json()
    # Allocated from the session, not supplied by the client.
    assert student["roll_no"] == "2024-001"
    assert student["session"]["label"] == "2024-2026"
    # Dashes are stripped so the unique index actually means something.
    assert student["b_form_cnic"] == "4210112345671"
    assert student["is_active"] is True
    assert student["has_password"] is True
    # The hash must never be exposed.
    assert "hashed_password" not in student
    assert "password" not in student

    fetched = await db_client.get(f"{STUDENTS}/{student['id']}", headers=_auth(token))
    assert fetched.status_code == 200
    assert fetched.json()["full_name"] == "Ada Lovelace"

    updated = await db_client.patch(
        f"{STUDENTS}/{student['id']}",
        headers=_auth(token),
        json={"last_name": "King"},
    )
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Ada King"
    # An omitted field keeps its value rather than being nulled by the default.
    assert updated.json()["email"] == "ada@test.edu"


async def test_student_without_password_reports_has_password_false(
    db_client, make_user, make_session
):
    await make_user("root@test.edu", roles=["super_admin"])
    token = await _staff_token(db_client, "root@test.edu")
    session_id = await make_session(2024)

    created = await db_client.post(
        STUDENTS,
        headers=_auth(token),
        json={"session_id": session_id, "first_name": "No", "last_name": "Creds"},
    )
    assert created.status_code == 201
    assert created.json()["has_password"] is False


async def test_duplicate_cnic_conflicts(db_client, make_user, make_session):
    """Roll numbers are generated and cannot collide; CNICs are client-supplied."""
    await make_user("root@test.edu", roles=["super_admin"])
    token = await _staff_token(db_client, "root@test.edu")
    session_id = await make_session(2024)

    body = {
        "session_id": session_id,
        "first_name": "First",
        "last_name": "Student",
        "b_form_cnic": "4210112345671",
    }
    assert (
        await db_client.post(STUDENTS, headers=_auth(token), json=body)
    ).status_code == 201

    # Same number, typed with dashes: it must normalize to the same value.
    dup = await db_client.post(
        STUDENTS,
        headers=_auth(token),
        json={**body, "first_name": "Second", "b_form_cnic": "42101-1234567-1"},
    )
    assert dup.status_code == 409
    assert "CNIC" in dup.json()["error"]["message"]


async def test_listing_is_paginated(db_client, make_user, make_session):
    await make_user("root@test.edu", roles=["super_admin"])
    token = await _staff_token(db_client, "root@test.edu")
    session_id = await make_session(2024)

    for i in range(3):
        await db_client.post(
            STUDENTS,
            headers=_auth(token),
            json={
                "session_id": session_id,
                "first_name": "Student",
                "last_name": str(i),
            },
        )

    page = await db_client.get(f"{STUDENTS}?limit=2&offset=0", headers=_auth(token))
    assert page.status_code == 200
    body = page.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["limit"] == 2


async def test_teacher_can_read_but_not_write_students(
    db_client, make_user, make_session
):
    """The seeded teacher role carries students:read but not students:write."""
    await make_user("teacher@test.edu", roles=["teacher"])
    token = await _staff_token(db_client, "teacher@test.edu")
    session_id = await make_session(2024)

    assert (await db_client.get(STUDENTS, headers=_auth(token))).status_code == 200

    denied = await db_client.post(
        STUDENTS,
        headers=_auth(token),
        json={"session_id": session_id, "first_name": "No", "last_name": "Pe"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["details"]["missing_permissions"] == ["students:write"]


async def test_deactivating_a_student_revokes_their_sessions(
    db_client, make_user, make_session
):
    await make_user("root@test.edu", roles=["super_admin"])
    token = await _staff_token(db_client, "root@test.edu")
    session_id = await make_session(2024)

    created = await db_client.post(
        STUDENTS,
        headers=_auth(token),
        json={
            "session_id": session_id,
            "first_name": "Ada",
            "last_name": "Lovelace",
            "password": "password123",
        },
    )
    student_id = created.json()["id"]
    roll_no = created.json()["roll_no"]

    await db_client.post(
        "/api/v1/auth/student/login",
        json={"roll_no": roll_no, "password": "password123"},
    )

    deactivated = await db_client.patch(
        f"{STUDENTS}/{student_id}", headers=_auth(token), json={"is_active": False}
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    assert (await db_client.post("/api/v1/auth/student/refresh")).status_code == 401
    assert (
        await db_client.post(
            "/api/v1/auth/student/login",
            json={"roll_no": roll_no, "password": "password123"},
        )
    ).status_code == 401
