# syntax=docker/dockerfile:1.7

# =============================================================================
# Stage 1 - builder: resolve and install dependencies into an isolated venv.
# =============================================================================
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only what the build backend needs first, so dependency installation is
# cached independently from source changes.
COPY pyproject.toml README.md ./
COPY modules ./modules

RUN pip install --upgrade pip \
    && pip install .

# =============================================================================
# Stage 2 - runtime: slim image with just the venv and the application code.
# =============================================================================
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH"

RUN groupadd --system app && useradd --system --gid app --home-dir /app app

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

COPY --chown=app:app modules ./modules
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app alembic.ini main.py worker.py ./

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status == 200 else 1)"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# =============================================================================
# Stage 3 - dev: the test toolchain, kept out of the runtime image entirely.
# =============================================================================
FROM builder AS dev

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN pip install ".[dev]"

WORKDIR /app

CMD ["pytest"]
