#!/usr/bin/env bash
set -e

PGDATA=/data/postgres

# ── Init PostgreSQL data dir on first run ────────────────────────────
if [ ! -f "$PGDATA/PG_VERSION" ]; then
    echo "[init] Initializing PostgreSQL data directory..."
    mkdir -p "$PGDATA"
    chown postgres:postgres "$PGDATA"
    gosu postgres /usr/lib/postgresql/15/bin/initdb \
        -D "$PGDATA" \
        --no-locale \
        --encoding=UTF8

    # Allow trust for postgres superuser (port 5432 is NOT exposed to host)
    cat >> "$PGDATA/pg_hba.conf" << 'EOF'
# All-in-one: loopback trust (port 5432 unexposed to host)
host    all    all    127.0.0.1/32    trust
EOF
    echo "[init] PostgreSQL initialized"
fi

# ── Ensure runtime dirs exist ────────────────────────────────────────
mkdir -p /data/uploads /data/outputs /var/log/supervisor

# ── Persist SECRET_KEY across restarts ──────────────────────────────
SECRET_KEY_FILE="/data/.secret_key"
if [ -z "${SECRET_KEY:-}" ]; then
    if [ -f "$SECRET_KEY_FILE" ]; then
        export SECRET_KEY="$(cat "$SECRET_KEY_FILE")"
    else
        export SECRET_KEY="$(tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c 64)"
        echo "$SECRET_KEY" > "$SECRET_KEY_FILE"
        chmod 600 "$SECRET_KEY_FILE"
        echo "[init] Generated new SECRET_KEY (persisted to volume)"
    fi
fi

# ── Internal service defaults ────────────────────────────────────────
: "${DATABASE_URL:=postgresql+asyncpg://babeldoc:babeldoc@127.0.0.1:5432/babeldoc}"
: "${UPLOAD_DIR:=/data/uploads}"
: "${OUTPUT_DIR:=/data/outputs}"
export DATABASE_URL UPLOAD_DIR OUTPUT_DIR

exec /usr/bin/supervisord -n -c /etc/supervisor/conf.d/babeldoc.conf
