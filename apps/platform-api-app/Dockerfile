FROM python:3.13-slim AS builder

WORKDIR /build

# Install build deps for packages that need compilation (psycopg, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# --- Copy dependency manifests ---
# Platform API
COPY apps/platform-api-app/pyproject.toml /build/apps/platform-api-app/
# Root package
COPY pyproject.toml /build/
COPY setup.py /build/
COPY requirements.txt /build/
COPY ai_data_science_team/_version.py /build/ai_data_science_team/

# Install root deps first (cached unless deps change)
RUN pip install --no-cache-dir -r /build/requirements.txt

# Install platform-api deps
RUN pip install --no-cache-dir "/build/apps/platform-api-app/."


# =========================================================================
# Runtime image
# =========================================================================
FROM python:3.13-slim

WORKDIR /app

# Runtime deps only (no build toolchain)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# --- Copy application code ---
COPY apps/platform-api-app/platform_api /app/platform_api
COPY apps/platform-api-app/alembic /app/alembic
COPY apps/platform-api-app/alembic.ini /app/alembic.ini

# Copy the ai_data_science_team package (agents, tools, etc.)
COPY ai_data_science_team /app/ai_data_science_team
COPY plugins /app/plugins

# Environment defaults
ENV API_HOST=0.0.0.0
ENV API_PORT=8000
ENV PYTHONUNBUFFERED=1
ENV DEPLOYMENT_PROFILE=release
ENV ARTIFACT_STORAGE_BACKEND=local

EXPOSE 8000

# Health check
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -sf http://localhost:8000/healthz || exit 1

# Entrypoint: run migrations, then start the API
CMD ["sh", "-c", "\
    alembic upgrade head && \
    uvicorn platform_api.asgi:app --host 0.0.0.0 --port ${API_PORT:-8000} \
"]
