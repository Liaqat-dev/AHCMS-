"""RBAC tests: permission guards, runtime role creation, dynamic permissions.

Only two roles are seeded — ``super_admin`` and ``teacher``. Anything else is
created at runtime, which is what most of these tests exercise.
"""

from __future__ import annotations

LOGIN = "/api/v1/auth/login"


async def _token(db_client, email: str, password: str = "password123") -> str:
    resp = await db_client.post(LOGIN, json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _role_named(db_client, token: str, name: str) -> dict:
    resp = await db_client.get("/api/v1/roles", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    return next(r for r in resp.json() if r["name"] == name)


async def test_only_two_roles_are_seeded(db_client, make_user):
    await make_user("root@test.edu", roles=["super_admin"])
    token = await _token(db_client, "root@test.edu")

    resp = await db_client.get("/api/v1/roles", headers=_auth(token))
    assert resp.status_code == 200
    roles = {r["name"]: r for r in resp.json()}
    assert set(roles) == {"super_admin", "teacher"}
    # Students are not a role at all.
    assert "student" not in roles
    assert roles["super_admin"]["is_system"] is True
    assert roles["teacher"]["is_system"] is False


async def test_permission_guard_forbids_teacher(db_client, make_user):
    await make_user("teacher@test.edu", roles=["teacher"])
    token = await _token(db_client, "teacher@test.edu")

    resp = await db_client.get("/api/v1/users", headers=_auth(token))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


async def test_super_admin_creates_user_and_assigns_roles(db_client, make_user):
    await make_user("root@test.edu", roles=["super_admin"])
    token = await _token(db_client, "root@test.edu")

    created = await db_client.post(
        "/api/v1/users",
        headers=_auth(token),
        json={
            "email": "new.teacher@test.edu",
            "password": "password123",
            "full_name": "New Teacher",
            "roles": ["teacher"],
        },
    )
    assert created.status_code == 201, created.text
    user = created.json()
    assert user["roles"] == ["teacher"]

    # Duplicate email → 409 conflict.
    dup = await db_client.post(
        "/api/v1/users",
        headers=_auth(token),
        json={"email": "new.teacher@test.edu", "password": "password123", "roles": []},
    )
    assert dup.status_code == 409

    # Unknown role → 404.
    bad = await db_client.put(
        f"/api/v1/users/{user['id']}/roles",
        headers=_auth(token),
        json={"roles": ["wizard"]},
    )
    assert bad.status_code == 404


async def test_super_admin_creates_role_and_grants_it(db_client, make_user, make_session):
    """The core of dynamic RBAC: a brand-new role, created and used at runtime."""
    await make_user("root@test.edu", roles=["super_admin"])
    await make_user("clerk@test.edu", roles=["teacher"])
    root_token = await _token(db_client, "root@test.edu")
    session_id = await make_session(2024)

    created = await db_client.post(
        "/api/v1/roles",
        headers=_auth(root_token),
        json={
            "name": "registrar",
            "description": "Manages student records",
            "permissions": ["students:read", "students:write"],
        },
    )
    assert created.status_code == 201, created.text
    role = created.json()
    assert role["is_system"] is False
    assert sorted(role["permissions"]) == ["students:read", "students:write"]

    # A teacher cannot create students...
    clerk_token = await _token(db_client, "clerk@test.edu")
    assert (
        await db_client.post(
            "/api/v1/students",
            headers=_auth(clerk_token),
            json={"session_id": session_id, "first_name": "Ann", "last_name": "Lee"},
        )
    ).status_code == 403

    # ...until granted the new role, and re-authenticated.
    users = await db_client.get("/api/v1/users", headers=_auth(root_token))
    clerk = next(u for u in users.json()["items"] if u["email"] == "clerk@test.edu")
    assigned = await db_client.put(
        f"/api/v1/users/{clerk['id']}/roles",
        headers=_auth(root_token),
        json={"roles": ["teacher", "registrar"]},
    )
    assert assigned.status_code == 200
    assert sorted(assigned.json()["roles"]) == ["registrar", "teacher"]

    fresh = await _token(db_client, "clerk@test.edu")
    allowed = await db_client.post(
        "/api/v1/students",
        headers=_auth(fresh),
        json={"session_id": session_id, "first_name": "Ann", "last_name": "Lee"},
    )
    assert allowed.status_code == 201, allowed.text


async def test_duplicate_role_name_conflicts(db_client, make_user):
    await make_user("root@test.edu", roles=["super_admin"])
    token = await _token(db_client, "root@test.edu")

    body = {"name": "registrar", "permissions": []}
    assert (
        await db_client.post("/api/v1/roles", headers=_auth(token), json=body)
    ).status_code == 201
    dup = await db_client.post("/api/v1/roles", headers=_auth(token), json=body)
    assert dup.status_code == 409


async def test_system_role_cannot_be_edited_or_deleted(db_client, make_user):
    """super_admin is immutable, so RBAC administration can't be locked out."""
    await make_user("root@test.edu", roles=["super_admin"])
    token = await _token(db_client, "root@test.edu")
    root_role = await _role_named(db_client, token, "super_admin")

    stripped = await db_client.put(
        f"/api/v1/roles/{root_role['id']}/permissions",
        headers=_auth(token),
        json={"permissions": ["courses:read"]},
    )
    assert stripped.status_code == 400

    renamed = await db_client.patch(
        f"/api/v1/roles/{root_role['id']}",
        headers=_auth(token),
        json={"name": "root"},
    )
    assert renamed.status_code == 400

    deleted = await db_client.delete(
        f"/api/v1/roles/{root_role['id']}", headers=_auth(token)
    )
    assert deleted.status_code == 400

    # Still holds every permission afterwards.
    after = await _role_named(db_client, token, "super_admin")
    assert "roles:write" in after["permissions"]


async def test_role_deletion_requires_no_holders(db_client, make_user):
    await make_user("root@test.edu", roles=["super_admin"])
    token = await _token(db_client, "root@test.edu")

    created = await db_client.post(
        "/api/v1/roles",
        headers=_auth(token),
        json={"name": "temporary", "permissions": ["courses:read"]},
    )
    role_id = created.json()["id"]

    user = await db_client.post(
        "/api/v1/users",
        headers=_auth(token),
        json={
            "email": "holder@test.edu",
            "password": "password123",
            "roles": ["temporary"],
        },
    )
    assert user.status_code == 201

    in_use = await db_client.delete(f"/api/v1/roles/{role_id}", headers=_auth(token))
    assert in_use.status_code == 409

    # Reassign, then the delete succeeds.
    await db_client.put(
        f"/api/v1/users/{user.json()['id']}/roles",
        headers=_auth(token),
        json={"roles": ["teacher"]},
    )
    freed = await db_client.delete(f"/api/v1/roles/{role_id}", headers=_auth(token))
    assert freed.status_code == 204


async def test_teacher_cannot_edit_role_permissions(db_client, make_user):
    await make_user("teacher@test.edu", roles=["teacher"])
    await make_user("root@test.edu", roles=["super_admin"])
    teacher_token = await _token(db_client, "teacher@test.edu")
    root_token = await _token(db_client, "root@test.edu")

    teacher_role = await _role_named(db_client, root_token, "teacher")
    denied = await db_client.put(
        f"/api/v1/roles/{teacher_role['id']}/permissions",
        headers=_auth(teacher_token),
        json={"permissions": ["courses:read"]},
    )
    assert denied.status_code == 403


async def test_dynamic_permission_change_applies_on_next_login(db_client, make_user):
    await make_user("root@test.edu", roles=["super_admin"])
    await make_user("teacher@test.edu", roles=["teacher"])
    root_token = await _token(db_client, "root@test.edu")

    teacher_token = await _token(db_client, "teacher@test.edu")
    assert (
        await db_client.get("/api/v1/users", headers=_auth(teacher_token))
    ).status_code == 403

    teacher_role = await _role_named(db_client, root_token, "teacher")
    grant = await db_client.put(
        f"/api/v1/roles/{teacher_role['id']}/permissions",
        headers=_auth(root_token),
        json={"permissions": teacher_role["permissions"] + ["users:read"]},
    )
    assert grant.status_code == 200

    # Old token unchanged (perms are embedded), fresh login picks it up.
    assert (
        await db_client.get("/api/v1/users", headers=_auth(teacher_token))
    ).status_code == 403
    fresh_token = await _token(db_client, "teacher@test.edu")
    assert (
        await db_client.get("/api/v1/users", headers=_auth(fresh_token))
    ).status_code == 200


async def test_permission_catalog_listing(db_client, make_user):
    await make_user("root@test.edu", roles=["super_admin"])
    token = await _token(db_client, "root@test.edu")
    resp = await db_client.get("/api/v1/roles/permissions", headers=_auth(token))
    assert resp.status_code == 200
    codes = {p["code"] for p in resp.json()}
    assert {"students:read", "roles:write", "users:write"} <= codes
