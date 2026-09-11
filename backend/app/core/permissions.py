"""Permission catalog, seed roles, and the default role → permission mapping.

Permissions are a fixed catalog of ``resource:action`` codes seeded into the
``permissions`` table. Roles are **dynamic**: ``super_admin`` creates new roles
and edits which permissions each one carries at runtime through
``/api/v1/roles``. The mapping below is only the initial seed.

**Actions are read / create / update / delete.** They were once read/write,
where "write" meant all three of the others at once. Deleting an attendance
register throws away a day's marks for a whole class, and that should not be
the same grant as correcting one student's mark.

A code exists only where an endpoint backs it. There is no ``DELETE /students``
and no way to edit an academic session, so ``students:delete`` and
``sessions:update`` are not minted — a permission that can be granted but does
nothing is worse than a coarse one, because it implies a control that is not
there. The roles grid renders an absent action as "–".

Students are deliberately **not** a role. A student is not a ``User`` at all —
they authenticate against the ``students`` table with a roll number and
password and reach only their own portal (see ``app.api.v1.student_portal``).
"""

from __future__ import annotations

# ----- Seed roles ----------------------------------------------------------
ROLE_SUPER_ADMIN = "super_admin"
ROLE_TEACHER = "teacher"

# Only these two exist out of the box; more are created at runtime.
ALL_ROLES = (ROLE_SUPER_ADMIN, ROLE_TEACHER)

# Roles the API refuses to rename, delete, or strip permissions from. Without
# this, a super-admin could revoke `roles:update` from their own only role and
# permanently lock every account out of RBAC administration.
SYSTEM_ROLES = (ROLE_SUPER_ADMIN,)

ROLE_DESCRIPTIONS: dict[str, str] = {
    ROLE_SUPER_ADMIN: "Full access, including role and permission management",
    ROLE_TEACHER: "Teaching faculty",
}

# ----- Permissions (resource:action) ---------------------------------------
# No students:delete — a student record is deactivated, never removed, so no
# endpoint deletes one.
STUDENTS_READ = "students:read"
STUDENTS_CREATE = "students:create"
STUDENTS_UPDATE = "students:update"

FACULTY_READ = "faculty:read"
FACULTY_CREATE = "faculty:create"
FACULTY_UPDATE = "faculty:update"
FACULTY_DELETE = "faculty:delete"

ENROLLMENTS_READ = "enrollments:read"
ENROLLMENTS_CREATE = "enrollments:create"
ENROLLMENTS_UPDATE = "enrollments:update"
ENROLLMENTS_DELETE = "enrollments:delete"

# Staff accounts are deactivated rather than deleted, so there is no delete.
USERS_READ = "users:read"
USERS_CREATE = "users:create"
USERS_UPDATE = "users:update"

ROLES_READ = "roles:read"
ROLES_CREATE = "roles:create"
ROLES_UPDATE = "roles:update"
ROLES_DELETE = "roles:delete"

# Academic sessions: the two-year batch a student belongs to. Creating one is
# an administrative act -- the batch's start year is baked into every roll
# number it issues -- so it is kept separate from the student permissions. A
# session is write-once, so it has neither update nor delete.
SESSIONS_READ = "sessions:read"
SESSIONS_CREATE = "sessions:create"

# Programs: the courses of study students are admitted to ("ENG", "BBA"). The
# code is a short form other records quote, so renaming or deleting one is
# administrative -- hence its own permissions rather than a shared one.
PROGRAMS_READ = "programs:read"
PROGRAMS_CREATE = "programs:create"
PROGRAMS_UPDATE = "programs:update"
PROGRAMS_DELETE = "programs:delete"

# Classes: the teaching groups inside a program. Kept separate from the program
# permissions so a role can be allowed to open a new class for next term
# without also being able to rename or delete the program it sits in.
CLASSES_READ = "classes:read"
CLASSES_CREATE = "classes:create"
CLASSES_UPDATE = "classes:update"
CLASSES_DELETE = "classes:delete"

# Subjects: taught subjects, shared across classes. Attaching a subject to a
# class is an update -- it edits the subject's own class list.
SUBJECTS_READ = "subjects:read"
SUBJECTS_CREATE = "subjects:create"
SUBJECTS_UPDATE = "subjects:update"
SUBJECTS_DELETE = "subjects:delete"

# Attendance: the daily register per class. Opening and marking ship with the
# teacher role -- it is their daily job -- but deleting a register throws away
# a whole day's marks, so that is a separate grant.
ATTENDANCE_READ = "attendance:read"
ATTENDANCE_CREATE = "attendance:create"
ATTENDANCE_UPDATE = "attendance:update"
ATTENDANCE_DELETE = "attendance:delete"

# Exams: a paper sat by a class on a date, covering one subject or all of them.
EXAMS_READ = "exams:read"
EXAMS_CREATE = "exams:create"
EXAMS_UPDATE = "exams:update"
EXAMS_DELETE = "exams:delete"

# Marks are the one place ownership matters rather than role alone.
# ``marks:update`` lets you enter marks for **subjects you teach** -- the link
# being faculty.user_id. ``marks:update_any`` lifts that restriction, for the
# office correcting a paper whose teacher has left.
MARKS_READ = "marks:read"
MARKS_UPDATE = "marks:update"
MARKS_UPDATE_ANY = "marks:update_any"

PERMISSION_DESCRIPTIONS: dict[str, str] = {
    STUDENTS_READ: "View students",
    STUDENTS_CREATE: "Admit students",
    STUDENTS_UPDATE: "Edit students and set their portal passwords",
    FACULTY_READ: "View faculty",
    FACULTY_CREATE: "Add faculty",
    FACULTY_UPDATE: "Edit faculty",
    FACULTY_DELETE: "Delete faculty records",
    ENROLLMENTS_READ: "View enrollments",
    ENROLLMENTS_CREATE: "Enrol students in a class",
    ENROLLMENTS_UPDATE: "Move a student's class and change their subjects",
    ENROLLMENTS_DELETE: "Unenroll students",
    USERS_READ: "View staff accounts",
    USERS_CREATE: "Create staff accounts",
    USERS_UPDATE: "Edit staff accounts and assign roles",
    ROLES_READ: "View roles and permissions",
    ROLES_CREATE: "Create roles",
    ROLES_UPDATE: "Rename roles and change the permissions they carry",
    ROLES_DELETE: "Delete roles",
    SESSIONS_READ: "View academic sessions",
    SESSIONS_CREATE: "Create academic sessions (student batches)",
    PROGRAMS_READ: "View programs",
    PROGRAMS_CREATE: "Create programs",
    PROGRAMS_UPDATE: "Edit programs",
    PROGRAMS_DELETE: "Delete programs",
    CLASSES_READ: "View classes",
    CLASSES_CREATE: "Create classes",
    CLASSES_UPDATE: "Edit classes",
    CLASSES_DELETE: "Delete classes",
    SUBJECTS_READ: "View subjects",
    SUBJECTS_CREATE: "Create subjects",
    SUBJECTS_UPDATE: "Edit subjects and the classes they run in",
    SUBJECTS_DELETE: "Delete subjects",
    EXAMS_READ: "View exams",
    EXAMS_CREATE: "Schedule exams",
    EXAMS_UPDATE: "Edit exams",
    EXAMS_DELETE: "Delete exams",
    MARKS_READ: "View exam marks",
    MARKS_UPDATE: "Enter marks for subjects you teach",
    MARKS_UPDATE_ANY: "Enter marks for any subject",
    ATTENDANCE_READ: "View attendance registers",
    ATTENDANCE_CREATE: "Open attendance registers",
    ATTENDANCE_UPDATE: "Mark students on a register",
    ATTENDANCE_DELETE: "Delete attendance registers",
}

ALL_PERMISSIONS: tuple[str, ...] = tuple(PERMISSION_DESCRIPTIONS)

# Initial seed only — editable at runtime through the roles API.
DEFAULT_ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    ROLE_SUPER_ADMIN: ALL_PERMISSIONS,
    ROLE_TEACHER: (
        STUDENTS_READ,
        FACULTY_READ,
        ENROLLMENTS_READ,
        ENROLLMENTS_CREATE,
        ENROLLMENTS_UPDATE,
        ENROLLMENTS_DELETE,
        # Read-only by default: a teacher needs to see sessions to filter
        # students by intake. Granting sessions:create to a teacher's role is a
        # deliberate act a super-admin performs at runtime.
        SESSIONS_READ,
        # Same reasoning as sessions: a teacher needs to name a program, not
        # to create or rename one.
        PROGRAMS_READ,
        CLASSES_READ,
        SUBJECTS_READ,
        # Marking is the teacher's daily job, so these ship with the role.
        # Deleting a register throws away a day's marks, so that one does not.
        ATTENDANCE_READ,
        ATTENDANCE_CREATE,
        ATTENDANCE_UPDATE,
        # Scheduling an exam and marking one's own papers are both a teacher's
        # job. marks:update is scoped to the subjects they actually teach, so
        # it is safe to ship; marks:update_any is not.
        EXAMS_READ,
        EXAMS_CREATE,
        MARKS_READ,
        MARKS_UPDATE,
    ),
}
