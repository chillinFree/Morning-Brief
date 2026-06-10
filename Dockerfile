# Daily Brief Agent — container image for the main app.
#
# Build:   docker build -t daily-brief .
# Run:     docker run --rm -v "$PWD/var:/app/var" daily-brief dry-run
#
# The image installs the package so the `daily-brief` entrypoint is on PATH.
# The default source (file) and sender (console) need no secrets, so the
# demo path (`dry-run`) works out of the box.

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

# Application data needed for the zero-config demo and runtime.
COPY data ./data
COPY config ./config

# Writable locations for SQLite, previews, and workflow artifacts.
# Mount a volume at /app/var to persist these across runs.
RUN mkdir -p var runs

EXPOSE 8000

ENTRYPOINT ["daily-brief"]
CMD ["dry-run"]
