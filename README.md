# College Management System

A production-grade full-stack scaffold for a College Management System
(~200 students, low traffic), designed to run comfortably on **free tiers**.

- **Backend** — FastAPI (async SQLAlchemy 2.x + asyncpg), Alembic, Argon2, JWT,
  in-memory rate limiting, structured JSON logging, a consistent error envelope,
  and a request-id correlation middleware. Managed with **uv**.
- **Frontends** — **two** Angular (zoneless) + Tailwind apps, ESLint + Prettier,
  lazy-loaded routes: `frontend-staff/` for teachers and administrators, and
  `frontend-portal/` for students. Separate workspaces, separate deployments.
- **Database** — **Neon** serverless Postgres, in development and in production
  alike. Nothing to install or run locally.
- **No Docker, no Redis** — both services run natively. For a single low-traffic
  instance, rate limiting runs in-memory and sessions are stored in Postgres, so
  there's no paid dependency.

> **Status.** Authentication (both principals, end to end through the UI), RBAC,
> staff accounts, and student records are implemented and tested. `faculty`,
> `courses`, and `enrollments` are still empty routers — their models and
> permissions exist, but no endpoints yet.

## Who can sign in

There are two entirely separate kinds of principal.

**Staff** sign in with an email and hold roles. Two roles are seeded:

| Role          | Notes                                                              |
| ------------- | ------------------------------------------------------------------ |
| `super_admin` | Every permission. A *system* role: cannot be renamed, deleted, or have its permissions edited, so RBAC administration can never be locked out. |
| `teacher`     | Read access plus enrolment writes. Freely editable.                |

Any further role is **created at runtime** by a super-admin
(`POST /api/v1/roles`), and every role's permission set is edited live
(`PUT /api/v1/roles/{id}/permissions`). Permissions themselves are a fixed
catalog of `resource:action` codes (`app/core/permissions.py`).

**Students are not staff, and "student" is not a role.** A student is a row in
`students`, holds no roles and no permissions, and signs in at
`POST /api/v1/auth/student/login` with a **roll number and password**. The only
thing a student token opens is `GET /api/v1/student/me` — every staff endpoint
refuses it with 403. Staff create students and issue their passwords under the
`students:write` permission.

Because permissions are baked into the 15-minute access token, a permission
change takes effect on the holder's next login or refresh.

## Repository layout

```
.
├── backend/          # FastAPI app (see backend/ for details)
├── frontend-staff/   # Angular app for teachers + administrators  (:4200)
├── frontend-portal/  # Angular app for students                   (:4300)
├── scripts/          # Windows/PowerShell dev scripts
├── Makefile          # the same tasks for macOS/Linux
└── render.yaml       # Render Blueprint (backend, native Python runtime)
```

**Why two apps.** Staff and students are separate principals server-side — separate
logins, separate tokens, separate refresh cookies — and they deploy to separate
subdomains, so each gets its own browser origin and its own cookie jar. The cost is
that a handful of files (`TokenService`, the HTTP interceptors, the API error helper)
are duplicated in both; change one and check the other.

Note that the split buys *no* security by itself. The boundary is enforced entirely by
the API: a student token is refused by every staff endpoint with a 403.

## Prerequisites

| Tool     | Version                | Notes                                        |
| -------- | ---------------------- | -------------------------------------------- |
| Python   | 3.11+                  | `uv` is used if present, otherwise venv + pip |
| Node.js  | 20.19+ or 22.12+       | ships npm                                     |
| Neon     | free account           | https://neon.tech — provides the database     |

## 1. Create the database (Neon)

1. Sign up at [neon.tech](https://neon.tech) and create a project (name the
   database `cms`).
2. Open **Connect** and copy the connection string. It looks like:

   ```
   postgresql://USER:PASSWORD@ep-xxxx-xxxx.REGION.aws.neon.tech/cms?sslmode=require&channel_binding=require
   ```

Paste it into `backend/.env` as `DATABASE_URL` **exactly as Neon gives it to
you** — the app normalizes the scheme to the async driver and strips the
libpq-only query parameters that asyncpg rejects
(`Settings.sqlalchemy_database_uri` in `backend/app/core/config.py`).

## 2. Install and run

### Windows (PowerShell)

```powershell
.\scripts\setup.ps1        # backend venv + deps, both node_modules, backend\.env
# edit backend\.env -> DATABASE_URL
.\scripts\dev.ps1          # starts all three, each in its own window
```

Run the pieces separately if you prefer: `.\scripts\backend.ps1`,
`.\scripts\staff.ps1`, `.\scripts\portal.ps1`. Pass `-SkipPortal` to `dev.ps1` to
start only the backend and the staff app.

### macOS / Linux

```bash
make setup                 # uv sync + npm ci in both frontends
cp backend/.env.example backend/.env   # then edit DATABASE_URL
make dev                   # all three; or `make backend` / `make staff` / `make portal`
```

### Or by hand

```bash
# Backend  (from backend/)
uv sync                                   # or: python -m venv .venv && python scripts/pip_sync.py --dev
uv run alembic upgrade head               # create the schema in Neon
uv run python -m app.cli.seed_superadmin  # create the SUPERADMIN_* account
uv run uvicorn app.main:app --reload

# Staff app (from frontend-staff/), and the portal (from frontend-portal/)
npm ci
npm run start
```

Once everything is up:

- Staff app: http://localhost:4200 — sign in with `SUPERADMIN_EMAIL` / `SUPERADMIN_PASSWORD`
- Student portal: http://localhost:4300 — sign in with a roll number and the password
  staff issued for it (create a student from the staff app first)
- Backend API + docs: http://localhost:8000/docs
- Health check: http://localhost:8000/api/v1/health
- DB readiness: http://localhost:8000/api/v1/health/db

Each dev server proxies `/api` to `http://127.0.0.1:8000` via its own
`proxy.conf.json`, so both SPAs call the API **same-origin** and their httpOnly
refresh cookies stay first-party — the same shape as production.

> Neon's free tier suspends an idle project; the first request after a pause
> takes a second or two to wake it. The engine is configured with
> `pool_pre_ping` and a 300s `pool_recycle` to handle that transparently.

## Ports and troubleshooting

| Service        | Address                 | Override                           |
| -------------- | ----------------------- | ---------------------------------- |
| Backend        | `http://127.0.0.1:8000` | `.\scripts\backend.ps1 -Port 8010` |
| Staff app      | `http://localhost:4200` | `.\scripts\staff.ps1 -Port 4201`   |
| Student portal | `http://localhost:4300` | `.\scripts\portal.ps1 -Port 4301`  |

Both `proxy.conf.json` files target `http://127.0.0.1:8000` rather than
`localhost:8000` **on purpose**: Node 17+ resolves `localhost` to IPv6 `::1`
first, so a `localhost` target can silently reach a different server listening
on `::1` while uvicorn is bound to IPv4 only. If you change the backend port,
change it in **both** proxy files.

If a port is already taken (another project, a container, a previous run):

```powershell
# See what holds the port
Get-NetTCPConnection -LocalPort 8000 -State Listen |
    Select-Object LocalAddress, OwningProcess
```

Then either stop that process or start with `-Port`. Note that a backend on a
non-default port also needs the proxy target updated to match.

**`/api/v1/health/db` returns 503.** The API is up but cannot reach the
database — the usual cause is a `DATABASE_URL` that is still the placeholder,
has a typo, or belongs to a deleted Neon project. Liveness (`/api/v1/health`)
stays 200 in that state, which is how the two endpoints are meant to differ.

**Migrations need Postgres.** The Alembic revisions use the Postgres `now()`
default, so SQLite is not a drop-in substitute for local development. (The test
suite builds its schema with SQLAlchemy `create_all` instead, which is why it
runs on SQLite without a database server.)

## Configuration

All backend config is environment-driven (`backend/app/core/config.py`), read
from `backend/.env`. Key vars:

| Variable                | Purpose                                              |
| ----------------------- | ---------------------------------------------------- |
| `DATABASE_URL`          | Neon connection string (pasted as-is)                |
| `DB_SSL`                | `true` for Neon; `false` for a plain local Postgres  |
| `JWT_SECRET`            | Signing secret for access tokens (≥32 bytes)         |
| `ACCESS_TOKEN_TTL`      | Access-token lifetime (seconds)                      |
| `REFRESH_TOKEN_TTL`     | Refresh-token lifetime (seconds)                     |
| `MAX_SESSIONS_PER_USER` | Concurrent-session cap (default 5)                   |
| `SUPERADMIN_EMAIL/_PASSWORD` | Bootstrap admin account                         |
| `CORS_ORIGINS`          | Comma-separated allowed origins                      |
| `RATE_LIMIT_ENABLED`    | Toggle rate limiting                                 |
| `RATE_LIMIT_DEFAULT`    | e.g. `100/minute`                                    |

## Common tasks

`make <target>` on macOS/Linux; the Windows equivalents are spelled out below.

```bash
make migrate                       # apply migrations
make revision m="add students"     # autogenerate a migration
make seed                          # create/refresh the super-admin
make lint                          # ruff + mypy + eslint (both apps)
make test                          # backend tests (in-memory SQLite; no Neon needed)
make build                         # production build of both frontends
```

```powershell
# Windows equivalents, from backend\
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "add students"
.\.venv\Scripts\python.exe -m app.cli.seed_superadmin
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
```

Tests run against an in-memory SQLite database (`backend/tests/conftest.py`), so
they need no network and no Neon credentials.

## Deployment (free tier: Neon + Render + Vercel)

**1. Database — Neon.** The same project you created above, or a separate
production one.

**2. Backend — Render.** The `render.yaml` Blueprint deploys `backend/` as a
**native Python** web service (free plan) — no Docker image. Render runs
`scripts/pip_sync.py` to install dependencies from `pyproject.toml`, then
`scripts/start.sh`, which applies migrations and seeds the super-admin before
starting uvicorn on `$PORT`. Set these in the Render dashboard:

- `DATABASE_URL` → the Neon connection string
- `CORS_ORIGINS` → your Vercel domain

`ENV=prod`, `DEBUG=false`, `DB_SSL=true` and `PYTHON_VERSION` are set in the
Blueprint; `JWT_SECRET` is auto-generated. Health check path: `/api/v1/health`.

**3. Frontends — Vercel.** Create **two** projects from this repo, with root
directories `frontend-staff/` and `frontend-portal/`. In each one's `vercel.json`,
replace `YOUR-RENDER-BACKEND.onrender.com` with your Render URL. The rewrite forwards
`/api/*` to the backend so each SPA calls the API **same-origin** — this keeps the
httpOnly refresh cookie first-party, and means neither app needs CORS.

Point them at sibling subdomains, e.g. `teacher.example.edu` and
`student.example.edu`. The cookies are set without a `Domain` attribute, so they are
host-only and the two sessions stay independent. Never add a `Domain=` — that would
hand the cookie to every subdomain of the parent, and let any one of them toss a
cookie into the others.

## Notes

- **Angular version:** this scaffold targets Angular 21 (latest stable that runs on
  the current Node). To move to Angular 22, upgrade Node to ≥ 22.22.3 (or ≥ 24.15)
  and run `ng update @angular/core @angular/cli`.
- **Using a local Postgres instead of Neon:** point `DATABASE_URL` at it and set
  `DB_SSL=false`. Nothing else changes.
