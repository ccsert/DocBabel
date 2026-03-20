# ── Stage 1: Build frontend ──────────────────────────────────────────
FROM node:22-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ── Stage 2: All-in-one runtime ──────────────────────────────────────
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        postgresql-15 \
        postgresql-client-15 \
        nginx \
        supervisor \
        build-essential \
        libpq-dev \
        gosu \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/nginx/sites-enabled/default

# Install Python backend
WORKDIR /app
COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache-dir .

# Copy backend source (selective, skip generated/runtime dirs)
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini .
COPY backend/entrypoint.sh .

# Copy frontend build
COPY --from=frontend-builder /app/dist /usr/share/nginx/html

# Copy all-in-one configs
COPY docker/allinone/nginx.conf /etc/nginx/conf.d/babeldoc.conf
COPY docker/allinone/supervisord.conf /etc/supervisor/conf.d/babeldoc.conf
COPY docker/allinone/backend-start.sh /usr/local/bin/backend-start.sh
COPY docker/allinone/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /usr/local/bin/backend-start.sh

VOLUME ["/data"]
EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]
