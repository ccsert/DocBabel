#!/usr/bin/env bash
set -e

# ── Wait for PostgreSQL ──────────────────────────────────────────────
echo "[backend] Waiting for PostgreSQL..."
until pg_isready -h 127.0.0.1 -U postgres -q; do
    sleep 1
done
echo "[backend] PostgreSQL is ready"

# ── Create database/user on first run ────────────────────────────────
psql -h 127.0.0.1 -U postgres -tc \
    "SELECT 1 FROM pg_database WHERE datname = 'babeldoc'" | grep -q 1 || {
    echo "[backend] Creating database babeldoc..."
    psql -h 127.0.0.1 -U postgres -c \
        "CREATE DATABASE babeldoc ENCODING 'UTF8' LC_COLLATE='C' LC_CTYPE='C' TEMPLATE template0;"
}

psql -h 127.0.0.1 -U postgres -tc \
    "SELECT 1 FROM pg_roles WHERE rolname = 'babeldoc'" | grep -q 1 || {
    echo "[backend] Creating user babeldoc..."
    psql -h 127.0.0.1 -U postgres -c "CREATE USER babeldoc WITH PASSWORD 'babeldoc';"
    psql -h 127.0.0.1 -U postgres -c \
        "GRANT ALL PRIVILEGES ON DATABASE babeldoc TO babeldoc;"
    psql -h 127.0.0.1 -U postgres -d babeldoc -c \
        "GRANT ALL ON SCHEMA public TO babeldoc;" 2>/dev/null || true
}

# ── Run Alembic migrations (idempotent) ──────────────────────────────
echo "[backend] Running database migrations..."
cd /app
alembic upgrade head

# ── Start backend ────────────────────────────────────────────────────
echo "[backend] Starting uvicorn..."
exec uvicorn app.main:app --host 127.0.0.1 --port 8000
