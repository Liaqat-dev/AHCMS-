#!/usr/bin/env sh
# Production entrypoint (Render's startCommand): apply migrations, then serve.
# Render and other hosts inject $PORT; default to 8000 when run locally.
set -e

echo "==> Applying database migrations"
alembic upgrade head

echo "==> Ensuring super-admin account (no-op unless SUPERADMIN_* set)"
python -m app.cli.seed_superadmin

echo "==> Starting uvicorn on port ${PORT:-8000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
