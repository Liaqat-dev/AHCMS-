# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

College Management System: FastAPI backend (`backend/`) plus **two independent Angular
21 zoneless SPAs** — `frontend-staff/` (teachers + administrators) and
`frontend-portal/` (students) — against Neon serverless Postgres. No Docker, no Redis —
rate limiting is in-memory and sessions live in Postgres, so the whole thing runs on
free tiers.

The two apps are separate npm workspaces with their own `node_modules`, lockfile, and
Vercel project. They deploy to sibling subdomains (`teacher.` / `student.`), which is
why shared pieces (`TokenService`, the interceptors, `api-error.ts`, `models/api.ts`)
are **deliberately duplicated** rather than extracted — there is no shared library.
Keep an eye out when changing one: the counterpart usually needs the same edit.

Implemented: auth, RBAC, staff accounts (`users`), academic sessions, students + student
portal, and the academic structure — programs → classes → subjects → enrollment →
attendance. `faculty.py` is the one **empty placeholder router** left; its model and
permission codes exist, but no endpoints. None of the academic-structure endpoints have a
UI yet: neither SPA has a page for them.

## Academic structure

`programs` (name + a unique three-letter code like `ENG`, with `created_by` from the
caller's token) → `classes` (a name, unique within its program) → `subjects` (name, code,
`student_limit` default 30), joined to classes many-to-many through `class_subjects`.
**Subjects are deliberately shared across programs** — a Medical and an Engineering class
run the same English and differ only in Maths and Biology — so nothing checks that a
class's subjects belong to its program. Subjects have **no `teacher_id`**: whether a
teacher is a staff `User` with the `teacher` role or a row in `faculty` is deferred until
faculty is built out. Classes carry no seat limit; capacity is a per-subject concern.

**Enrollment** (`app/services/enrollments.py`) is where the invariants live. `enrollments`
holds one row per student with `UNIQUE(student_id)` — that constraint *is* the "a student
is in exactly one class" rule, and no history is kept: a move updates the row.
`subject_enrollments` keys the optional subject picks to the **enrollment**, not the
student, so a pick cannot exist without a class enrollment and dropping the enrollment
drops the picks. The one rule no foreign key can state — a picked subject must be one the
enrolled class runs — is checked in the service on every write that can break it, and
answers **422** (retrying never helps) where a full subject answers **409** (it might).
Moving class drops every pick, since they belonged to the old class; the response says how
many.

`subjects.student_count` is a **cache** of `subject_enrollments`, and
`app/services/capacity.py` is its only writer — a single conditional `UPDATE ... WHERE
student_count < student_limit` that cannot overbook, mirroring `allocate_roll_no`. It is
therefore *not* accepted by `POST`/`PATCH /subjects`; `python -m app.cli.reconcile_counts`
recomputes it if it ever drifts. Subject-set changes are applied as a **diff**, so
re-sending an unchanged list touches no counters.

Deletion is refusal, never cascade: a program with classes, a class with enrolled
students, a subject anybody has taken, or detaching a class from a subject its students
already take, are all **409** naming what is in the way.

Students never write enrollment — subject choice is recorded by staff. The portal stays
read-only, with `GET /api/v1/student/me/enrollment` and `/me/attendance` alongside
`/student/me`.

**Exams** (`app/services/exams.py`) are papers sat by a class on a date, covering one
subject or every subject the class runs. The subjects are **written down at creation** in
`exam_subjects` rather than derived later: a class's subject list changes, and an exam is a
record of the papers actually set. Unlike an attendance register an exam date **may be in
the future** — announcing one before it happens is the point. A mark row exists only once
somebody records something, so "not entered" stays distinct from a zero, and a CHECK keeps
"absent" and "scored" mutually exclusive.

**Marking is the only ownership rule in the app.** Everywhere else a permission code is the
whole answer; here the API also asks *who you are*. `subjects.teacher_id` names a `Faculty`
row while a request carries a `User`, so **`faculty.user_id`** (nullable, unique) joins
them — without it the rule is unenforceable, which is why it exists. `marks:update` lets
you mark the subjects you teach; `marks:update_any` is the office's override. The mark
sheet returns `can_mark` so the client renders read-only rather than offering a form the
API will refuse. See `services.exams.assert_may_mark`, which distinguishes "you are not the
teacher" from "your account is not linked to a staff file" — different problems, different
fixes.

**Attendance** (`app/services/attendance.py`) is one register per class per calendar day —
`UNIQUE(class_id, date)` on `attendance_sheets`. A day with **no sheet is a day the class
did not meet**, so there is no holiday calendar and percentages are computed over the
sheets that exist. Statuses are `present`, `absent`, `leave` (a `CHECK`, not a Postgres
ENUM, so adding one is a constraint change rather than a locking type alteration).

`attendance_records` key on `student_id`, **not** on the enrollment — the opposite of
`subject_enrollments`, deliberately: a subject choice only means anything inside the
enrollment that owns it, while an attendance mark is a fact about a day that already
happened and must survive a class move. A student with no record is **unmarked**, which is
neither present nor absent; rows exist only once somebody marks. Reading a sheet joins the
*current* roster, so students who left after being marked come back flagged `off_roster`
rather than silently dropped.

**A student's register starts on their enrolment day.** A sheet's roster is the students
whose `enrolled_at` falls on or before its date, so nobody opens with a week of absences
for a class they had not joined, and `eligible_days` in the per-student report is counted
the same way. `percentage` is present ÷ (present + absent) — `leave` is excluded from the
denominator — and is `null`, not `0.0`, when there is nothing to divide by.

Marking is `attendance:write`, which unlike every other write permission **ships with the
`teacher` role**: any staff member may mark any class, there is no ownership. Sheets stay
editable indefinitely; every record carries its own `marked_by_id`/`marked_at`, which is
what makes that safe.

**Dates are the college's, never the server's.** `COLLEGE_TIMEZONE` (default
`Asia/Karachi`) and `app/core/clock.py` are the only place "today" is computed — Render
runs UTC, where 1am in Karachi is still yesterday. Never `CAST` a stored timestamp to a
date in SQL to compare it with a sheet date: Postgres would cast in the *server's* zone
and SQLite has no date type at all. `clock.end_of_day` / `to_college_date` exist for that
comparison. `tzdata` is a runtime dependency because Windows and slim Linux images ship no
tz database.

**Timestamps come from the app, not the database.** Every timestamp column carries a
Python `default=college_now` alongside its `server_default=func.now()`; the server default
is only a backstop for rows written outside the app. This is not belt-and-braces — a
database whose clock differs from the app's stamps `enrollments.enrolled_at` at the wrong
instant, and since a register's roster is "students enrolled on or before this date", a
student enrolled today then *cannot be marked present today*. (The dev Neon instance was
observed 12 hours ahead, which is exactly how this was found.) One clock decides what time
it is, and it is the same one that decides what "today" means.

## Commands

`make <target>` works on macOS/Linux (see `Makefile`). On Windows there is no `uv` on
PATH — drive everything through the venv interpreter from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m ruff check . ; .\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m ruff format .
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "msg"
.\.venv\Scripts\python.exe -m app.cli.seed_superadmin    # from SUPERADMIN_* in .env
.\.venv\Scripts\python.exe -m app.cli.reconcile_counts   # rebuild subject student_count
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Frontends: from `frontend-staff/` or `frontend-portal/`, `npm run start` (:4200 staff,
:4300 portal), `npm run build`, `npm run lint`, `npm run format`.
Both must be installed and linted separately. (`npm test` exists but see the
testing policy below.)

Windows dev scripts live in `scripts\` (`setup.ps1` installs all three dependency sets,
`dev.ps1` opens backend + both apps in their own windows, `backend.ps1 -Port`,
`staff.ps1 -Port`, `portal.ps1 -Port`).

**Migrations require Postgres**: the revisions use the Postgres `now()` default, so
SQLite is not a substitute for running the app locally.

## Testing policy — OFF by default

**Do not write tests, and do not run them, unless the user explicitly asks in that
message.** This overrides every default habit: no new test files, no test cases added
to existing files, no "I'll just add a quick test to verify", no `pytest` / `npm test`
runs as a verification step. Verify work with `ruff check` + `mypy`, `npm run lint`,
`npm run build`, or by exercising the running app instead.

The existing backend suite (`backend/tests/`) is **disabled, not deleted**:
`collect_ignore_glob = ["test_*.py"]` at the bottom of `backend/tests/conftest.py`
makes pytest collect nothing (exit code 5, "no tests ran"). The files and fixtures —
in-memory SQLite via aiosqlite, no Neon credentials needed — are intact. Re-enable by
deleting that one line, but only when asked. `make test` is likewise a no-op stub.

The frontends have no `.spec.ts` files; leave it that way unless asked.

## Backend architecture

Layering: `api/v1/*.py` (routing + permission dependencies + schema mapping) →
`services/*.py` (business logic, async SQLAlchemy) → `db/models/*.py`. Routers call
`await db.commit()` themselves; `get_db` only rolls back on exception.

**Two principal types, kept strictly apart.** The access token's `sub_type` claim is
`"user"` (staff, has roles/permissions) or `"student"` (roll-number login, no roles at
all). `get_current_user` / `get_current_student` in `app/api/deps.py` reject the wrong
kind with **403, not 401** — a student token can never fall through into a permission
check. "Student" is deliberately not a role; students are rows in `students`, and their
only endpoint is `GET /api/v1/student/me`.

**RBAC is token-baked.** `AuthContext.roles`/`.permissions` come from the JWT, never a
live DB read, so permission changes only take effect on the next login/refresh (access
TTL 15 min). Guard endpoints with `Depends(require_permissions(perm.X))` /
`require_roles(...)` from `app/api/deps.py`.

**Actions are read / create / update / delete**, not read/write. Deleting an attendance
register throws away a day's marks for a whole class, and that is not the same grant as
correcting one student's mark. **A code exists only where an endpoint backs it**: there is
no `students:delete`, `users:delete`, `sessions:update` or `sessions:delete`, because
students and staff accounts are deactivated rather than removed and a session is
write-once. A permission that can be granted but does nothing is worse than a coarse one —
it implies a control that is not there — and the roles grid renders an absent action as
"–". Revision `f2a3b4c5d6e7` did the split and carried every existing `:write` grant across
first, so no role lost access; narrowing one is now a click in the roles grid.

**Permissions are a fixed catalog; roles are dynamic.** `app/core/permissions.py` holds
the `resource:action` codes and the *initial seed* mapping only — super-admins create
roles and edit their permission sets at runtime via `/api/v1/roles`. `SYSTEM_ROLES`
(`super_admin`) cannot be renamed, deleted, or have permissions stripped, so RBAC
administration can't be locked out. Adding a permission means: add the constant +
description in `permissions.py`, and a migration that seeds the row.

**Sessions / refresh tokens** (`app/services/auth.py`, `app/db/models/session.py`): one
`RefreshSession` row per login, owned by a `User` *or* a `Student`. The httpOnly cookie
is `"{session_id}.{secret}"`; only `sha256(secret)` is stored. Each refresh rotates the
secret but keeps the session id — replaying an old secret against a live session is
treated as theft and revokes the whole session. Because rotation is destructive, the
frontends share **one in-flight refresh** across concurrent 401s (`AuthService`);
parallel refreshes would make the losers present a rotated secret and self-revoke.

Staff and students carry **separate cookies**: `cms_refresh` on `/api/v1/auth` and
`cms_refresh_student` on `/api/v1/auth/student` (`STUDENT_REFRESH_COOKIE_*` in
`config.py`). A single shared name let one login silently overwrite the other's session
whenever both were used in one browser. The staff path is a prefix of the student path,
so the staff cookie is still *sent* to `/auth/student/*` — harmless, since each endpoint
looks its own cookie up by name, and `rotate_session(expect=...)` rejects a cookie whose
principal is the wrong kind regardless.

**Errors** are raised as `AppError` subclasses from `app/exceptions/errors.py` and
always render as `{"error": {code, message, details, request_id}}`. Don't return ad-hoc
error JSON. Middleware order in `app/main.py` is deliberate: RequestID (outermost) →
CORS → CatchAll → RateLimit, so unhandled 500s keep CORS headers and a correlation id.

**Config**: everything flows through `Settings` in `app/core/config.py`; nothing else
reads `os.environ`. `sqlalchemy_database_uri` rewrites a pasted Neon libpq URL to
`postgresql+asyncpg` and strips `sslmode`/`channel_binding` (asyncpg rejects them —
TLS is passed via `connect_args` in `db/session.py`), so `DATABASE_URL` can be pasted
verbatim from the dashboard.

Ruff excludes `app/migrations/versions`. Line length 100.

## Frontend architecture

Both apps are zoneless Angular with standalone components and signals; no NgModules.
Routes lazy-load every feature. Providers are in `app/app.config.ts`.

The access token is held **in memory only** (`core/auth/token.service.ts`, a signal) —
never localStorage. Durability comes from the refresh cookie instead: `app.config.ts`
runs `provideAppInitializer(... auth.restore())`, which trades the cookie for a token
**before the router bootstraps**, so guards see a restored session after a reload rather
than bouncing to the login page.

`authInterceptor` attaches the bearer token, sets `withCredentials: true`, and on a 401
refreshes once and replays the request; a 401 from an endpoint in its own `AUTH_ENDPOINTS`
list is a real answer, not an expired token, and is never retried (that would loop).

Each app calls the API **same-origin** so its cookie stays first-party: in dev via its
own `proxy.conf.json`, in production via the rewrite in its own `vercel.json` (replace
the placeholder Render host in **both**). The proxies target `127.0.0.1:8000`, not
`localhost` — Node 17+ resolves `localhost` to `::1` first while uvicorn binds IPv4
only. Change every copy if the backend port changes.

**Design tokens live in `frontend-staff/src/theme.css`** and are the one place colours are
defined. Two layers: a raw palette (`--petrol-600`, `--stone-100`) and semantic tokens
(`--t-accent`, `--t-canvas`, `--t-ink`, …). Components only ever use the semantic layer, so
retheming is editing hex values in that file and nothing else. Every token is redefined
under `.dark` — dark is a designed set, not an inversion. Tailwind sees them through
**`@theme inline`**, which is load-bearing: plain `@theme` would bake today's hex into each
utility and the theme switch would do nothing. Dark mode is a `dark` class on `<html>`
driven by `core/theme.service.ts` (so an explicit choice beats the OS), with a tiny inline
script in `index.html` applying it before Angular boots to avoid a white flash.

Feature pages are thin because the repeated parts live once: `core/api/crud.ts` is a
`CrudApi` base (list/get/create/update/remove over `/api/v1/<path>`) that each domain
service extends, `core/api/domain.ts` mirrors the backend row shapes, and
`shared/list-state.ts` holds the rows/total/paging/loading/error a list page needs —
including a sequence guard that drops stale responses, so typing in a search box cannot
leave the slowest reply on screen.

Shared primitives are in `shared/ui/` — `Button` (an **attribute** on a real `<button>`/`<a>`,
so `type="submit"`, form association and `routerLink` keep working), `Card` (bordered panel,
**no shadow in any variant**), `Modal` (native `<dialog>` + `showModal()`, which gives
focus trap, Escape, focus restore and top-layer for free), plus `Badge`, `Field`, `Empty`,
`PageHeader`, `Pagination` and the `controls.ts` class strings shared by inputs and tables.

Two Tailwind traps worth knowing: class names must be whole literals (Tailwind scans source
as text, so a class built by interpolation is never generated), and **never give a state
class a "resting" counterpart of the same property** — `before:bg-transparent` alongside
`before:bg-accent` is the same specificity, and Tailwind's own source order decides which
wins, silently.

**`frontend-staff/`** — domain pages nest under `layout/shell` behind `staffGuard`. The
shell is a full-width navbar with a sidebar beneath it: collapsible to icons on `lg+`
(persisted in `localStorage`), and below `lg` the sidebar's contents open as a panel
*under* the navbar from a hamburger, pushing content down rather than overlaying it.

`subjects.teacher_id` points at **`faculty`**, not at `users`: teaching is a fact about a
person on the college's books, and plenty of them never sign in. It is nullable, and
`ON DELETE RESTRICT` — `services.faculty.delete_member` refuses first, naming the subjects,
because a subject quietly losing its teacher while somebody tidies a personnel file is the
kind of change nobody notices until a timetable is printed. Marking the member former is
the usual answer.

When a service changes a foreign key and then re-reads the row, **expire the instance
first** and refetch by the id it was passed, not by `instance.id`: a plain re-query will not
overwrite a relationship the identity map already has loaded (so a cleared assignment comes
back still naming the old teacher), and reading an attribute off an expired instance is a
synchronous lazy load, which is an error under asyncio.

`faculty` is a personnel register, not an account system: faculty are not `User` rows and
hold no permissions, so someone who both teaches and administers has two records. Only an
employee number and a name are required, and `missing_fields` reports the rest — the same
shape as a student's admission file, sharing the CNIC and cell-number normalizers in
`app/schemas/fields.py`. Someone who leaves is marked inactive rather than deleted, so old
records can still name them.

Two record forms live on their own pages rather than in a modal. Admission
(`features/students/new-student.ts`) uses **numbered steps** because an admission happens
in an order — you cannot enrol someone who does not exist yet. The faculty file
(`features/faculty/faculty-form.ts`) uses **tabs**, because qualifications and salary are
facets of one record with no order between them, and an edit goes straight to the tab it
came for. Creating on `/faculty/new` replaces the URL with `/faculty/:id/edit` once saved,
so a reload or a shared link lands on the record.

Admission (`features/students/new-student.ts`) is a numbered wizard, but deliberately
**not a gate**: step 1 writes the student and allocates the roll number, and each later
step saves on its own, so the form can be abandoned without losing the admission. That
mirrors the backend, where only a name and an intake are required and `missing_fields`
reports the rest. **Attachments, Fees, faculty Salary and the further-degrees list are interface only** — no
such endpoints exist, and each says so on screen rather than appearing to save.

The **Roles** page (`features/roles/roles.ts`) is the runtime RBAC surface, and it is
administrator-only in the same way everything else is gated: `data.nav.permission` is
`roles:read`, which ships only with `super_admin`, so the sidebar hides it, `navGuard`
redirects a direct URL to the dashboard, and the API answers 403 — three layers off one
permission code, with no hardcoded role check anywhere. Permissions are `resource:action`,
so the page is a resource × action grid rather than a flat checklist: the grid's shape is
the codes' shape. `super_admin` is a system role and renders locked, because an
administrator who can strip their own `roles:write` can lock everyone out.

**The sidebar is built from the router config** (`layout/nav.ts`), not a hand-kept list:
a child route of the shell with `data.nav = { label, icon, permission, group }` becomes a
section, and `navGuard` reads the same `permission`, so a section's permission is written
once. Adding a page means adding a route. Permission filtering here is cosmetic only: the
API re-checks every request. There is no registration
page — staff accounts are created by an admin under `users:write`, and the backend has
no sign-up endpoint.

**`frontend-portal/`** — one page (`features/profile`) behind `studentGuard`, because
`GET /api/v1/student/me` is the entire surface a student token can open. `TokenService`
here holds no roles or permissions, deliberately.

## Deployment

`render.yaml` deploys `backend/` on Render's native Python runtime (no Docker):
`scripts/pip_sync.py` installs from `pyproject.toml`, then `scripts/start.sh` migrates,
seeds the super-admin, and starts uvicorn on `$PORT`. `DATABASE_URL` and `CORS_ORIGINS`
are set in the dashboard.

The two frontends are **two Vercel projects** off this repo, with root directories
`frontend-staff/` and `frontend-portal/`, pointed at sibling subdomains. Each rewrites
`/api/*` to the same Render service, so both stay same-origin and neither needs CORS.

Because they share a parent domain, never pass `domain=` to `set_cookie` — a
`Domain=lms.com` cookie would be readable by every sibling subdomain, and any subdomain
could then toss a cookie into the others.
