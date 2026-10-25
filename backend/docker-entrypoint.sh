#!/bin/sh
set -e

echo "[entrypoint] Verifying infrastructure dependencies (PostgreSQL & Redis)..."
python -m app.wait_for_deps

# If RUN_MIGRATIONS is true and this is the main web service, execute Alembic migrations
if [ "$RUN_MIGRATIONS" = "true" ] || [ "$1" = "migrate" ]; then
    echo "[entrypoint] Running database migrations (alembic upgrade head)..."
    alembic upgrade head
    echo "[entrypoint] Database migrations applied successfully."
fi

if [ "$1" = "migrate" ]; then
    echo "[entrypoint] Migration task complete. Exiting."
    exit 0
fi

echo "[entrypoint] Starting process: $@"
exec "$@"
