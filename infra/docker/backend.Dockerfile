# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# MedAnalyser backend image.
#
# Multi-stage: dependencies are installed into a virtualenv in the builder and
# copied into a slim runtime that contains no compilers or build headers.
# Built for linux/amd64 and linux/arm64 (Apple Silicon) alike.
# ---------------------------------------------------------------------------

FROM python:3.11-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

# build-essential is needed by some wheels on arm64; it stays in this stage only.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only the dependency manifest first so this layer caches across code edits.
# A minimal package stub is enough for setuptools to build the project.
COPY backend/pyproject.toml ./pyproject.toml
COPY backend/app/__init__.py ./app/__init__.py

# Install the project to resolve its dependencies, then remove the project
# itself: the real source is mounted at /app in the runtime stage, and leaving
# this stub installed in site-packages would shadow it on `import app`.
RUN pip install --upgrade pip \
    && pip install . \
    && pip uninstall -y medanalyser-backend


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# curl is used by the container healthcheck below.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Never run the API as root.
RUN groupadd --system --gid 1001 medanalyser \
    && useradd --system --uid 1001 --gid medanalyser --create-home medanalyser

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=medanalyser:medanalyser backend/ /app/

# Uploaded medical reports live here when STORAGE_PROVIDER=local.
RUN mkdir -p /app/storage && chown medanalyser:medanalyser /app/storage
VOLUME ["/app/storage"]

USER medanalyser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
