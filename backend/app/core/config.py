"""Typed, environment-driven application settings.

All configuration flows through :class:`Settings` so the rest of the app never
reads ``os.environ`` directly. Values come from environment variables (and a
local ``.env`` file in development).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic_settings import BaseSettings, SettingsConfigDict

_ASYNCPG_SCHEME = "postgresql+asyncpg"
# Schemes a hosted provider hands out, which name a sync driver or none at all.
_SYNC_PG_SCHEMES = frozenset(
    {"postgres", "postgresql", "postgresql+psycopg", "postgresql+psycopg2"}
)
# libpq-only query parameters. SQLAlchemy forwards unrecognized query params to
# ``asyncpg.connect()`` as keyword arguments, where these raise TypeError; TLS
# is passed through ``connect_args`` instead (see app/db/session.py).
_LIBPQ_ONLY_PARAMS = frozenset({"sslmode", "channel_binding"})
# ``sslmode`` values that demand an encrypted connection.
_SSL_REQUIRED_MODES = frozenset({"require", "verify-ca", "verify-full"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # ----- App -----
    ENV: Literal["dev", "test", "prod"] = "dev"
    DEBUG: bool = False
    PROJECT_NAME: str = "College Management System API"
    # The college's own calendar. Attendance is dated by day, so "today" has to
    # mean today *here* — the server runs UTC on Render, where 1am Karachi is
    # still yesterday. An IANA name, not an offset, so a future DST change is a
    # tzdata update rather than a code change.
    COLLEGE_TIMEZONE: str = "Asia/Karachi"
    VERSION: str = "0.1.0"

    # ----- Database -----
    # Set this to the connection string from your provider's dashboard; it may
    # be pasted verbatim, as ``sqlalchemy_database_uri`` below normalizes it
    # into the async form the asyncpg driver accepts.
    DATABASE_URL: str = "postgresql+asyncpg://cms:cms@localhost:5432/cms"
    # Force TLS to the database. Managed Postgres (Neon) requires it; a plain
    # local Postgres does not. An ``sslmode`` in DATABASE_URL also implies it.
    DB_SSL: bool = False
    DB_ECHO: bool = False

    # ----- Security / JWT -----
    # ≥32 bytes (RFC 7518 minimum for HS256). Always override in prod.
    JWT_SECRET: str = "dev-insecure-change-me-0000000000000000"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_TTL: int = 15 * 60  # seconds (15 minutes)
    REFRESH_TOKEN_TTL: int = 30 * 24 * 60 * 60  # seconds (30 days)
    MAX_SESSIONS_PER_USER: int = 5

    # ----- Refresh cookie -----
    # Staff and students get *separate* cookies. They are distinct principals
    # with distinct sessions, and a browser keyed only by origin would let one
    # login silently overwrite the other's refresh token if they shared a name.
    REFRESH_COOKIE_NAME: str = "cms_refresh"
    # Scope the cookie to the auth endpoints only.
    REFRESH_COOKIE_PATH: str = "/api/v1/auth"
    # The student cookie is scoped one level deeper, so a request to the staff
    # refresh endpoint never carries it. (The staff cookie's path *is* a prefix
    # of the student one, so it is still sent to /auth/student/* — harmless,
    # since each endpoint looks its own cookie up by name.)
    STUDENT_REFRESH_COOKIE_NAME: str = "cms_refresh_student"
    STUDENT_REFRESH_COOKIE_PATH: str = "/api/v1/auth/student"
    COOKIE_SECURE: bool = False  # set true in prod (HTTPS)
    # Use "none" (requires COOKIE_SECURE=true) for cross-site deploys
    # (e.g. SPA on Vercel talking to the API on Render).
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"

    # ----- Super-admin bootstrap (used by `python -m app.cli.seed_superadmin`) -----
    SUPERADMIN_EMAIL: str | None = None
    SUPERADMIN_PASSWORD: str | None = None

    # ----- CORS (comma-separated origins) -----
    CORS_ORIGINS: str = "http://localhost:4200"

    # ----- Rate limiting (in-memory; single-instance free tier) -----
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_LOGIN: str = "10/minute"

    @property
    def sqlalchemy_database_uri(self) -> str:
        """``DATABASE_URL`` normalized for SQLAlchemy's asyncpg driver.

        Neon (and most hosted Postgres) hands out a libpq string of the form
        ``postgresql://…?sslmode=require&channel_binding=require``. This rewrites
        the scheme to name the async driver and drops the libpq-only parameters,
        so the dashboard value works without hand-editing. Non-Postgres URLs
        (e.g. SQLite in tests) pass through untouched.
        """
        parts = urlsplit(self.DATABASE_URL)
        if parts.scheme not in _SYNC_PG_SCHEMES and parts.scheme != _ASYNCPG_SCHEME:
            return self.DATABASE_URL
        query = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key not in _LIBPQ_ONLY_PARAMS
        ]
        return urlunsplit(
            (_ASYNCPG_SCHEME, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )

    @property
    def db_requires_ssl(self) -> bool:
        """Whether the database connection must negotiate TLS."""
        if self.DB_SSL:
            return True
        query = dict(parse_qsl(urlsplit(self.DATABASE_URL).query))
        return query.get("sslmode", "") in _SSL_REQUIRED_MODES

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_prod(self) -> bool:
        return self.ENV == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
