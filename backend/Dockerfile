FROM python:3.12-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
RUN python -m venv /opt/venv
COPY requirements.txt constraints.txt ./
RUN /opt/venv/bin/pip install -r requirements.txt

FROM python:3.12-slim-bookworm AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    PORT=8080 \
    HOME=/home/app

WORKDIR /app

# WeasyPrint necesita Pango/Cairo en runtime (no van en el wheel).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi8 \
    shared-mime-info \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home app
COPY --from=builder /opt/venv /opt/venv
# Copias explícitas: nunca incluir .env, tests ni el entorno virtual local.
COPY --chown=app:app app ./app
USER 10001:10001

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c 'import os, urllib.request; urllib.request.urlopen("http://127.0.0.1:" + os.environ.get("PORT", "8080") + "/health/live", timeout=3)'

# exec entrega SIGTERM a Uvicorn; un proceso por instancia de Cloud Run.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --timeout-graceful-shutdown 8"]
