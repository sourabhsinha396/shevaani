FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# postgresql-client is for pg_dump/pg_restore, which the nightly backup job and
# the restore drill shell out to. The client major version must be >= the
# server's (postgres:16 in compose), or pg_dump refuses with a version error.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential libpq-dev postgresql-client-16 \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first so edits to app/ don't bust the layer cache.
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install ".[dev]"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
