"""Aggregate all v1 routers under ``/api/v1``."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    attendance,
    auth,
    classes,
    enrollments,
    exams,
    faculty,
    health,
    programs,
    roles,
    sessions,
    student_portal,
    students,
    subjects,
    users,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
# Student portal: separate principal, separate login, own profile only.
api_router.include_router(student_portal.auth_router)
api_router.include_router(student_portal.portal_router)
api_router.include_router(users.router)
api_router.include_router(roles.router)
api_router.include_router(sessions.router)
api_router.include_router(programs.router)
api_router.include_router(classes.router)
api_router.include_router(subjects.router)
api_router.include_router(students.router)
api_router.include_router(faculty.router)
api_router.include_router(enrollments.router)
api_router.include_router(attendance.router)
api_router.include_router(exams.router)
api_router.include_router(attendance.router)
