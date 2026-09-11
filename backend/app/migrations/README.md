# Database migrations (Alembic, async)

- Create a revision after changing models:
  `uv run alembic revision --autogenerate -m "describe change"`
- Apply migrations: `uv run alembic upgrade head`

The migration environment reuses the app's async engine and reads
`Base.metadata`, so `DATABASE_URL` / `DB_SSL` from settings apply automatically.
On deploy, `scripts/start.sh` runs `alembic upgrade head` before the server starts.
