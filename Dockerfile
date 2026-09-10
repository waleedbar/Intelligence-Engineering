# SahaCore — the engine's HTTP surface and its test suite.
#
# ONE IMAGE, TWO JOBS, AND THAT IS DELIBERATE. It serves the API and it runs
# the suite, because the third requirement of this milestone is that the
# tests pass INSIDE the container -- and a test image built from different
# layers than the serving image proves nothing about the serving image. The
# cost is pytest and openpyxl in production, which is a few megabytes and no
# attack surface that `python` itself does not already have.
#
# The engine never opens a spreadsheet at runtime: the build_* extractors
# read the workbook and the engine reads the JSON they produced, which is
# committed. So no workbook is copied in, and the image cannot depend on one.

FROM python:3.12-slim AS base

# - PYTHONDONTWRITEBYTECODE: the filesystem is read-mostly; .pyc files
#   written at runtime just make the layer dirty.
# - PYTHONUNBUFFERED: without it, logs sit in a pipe buffer and a container
#   that dies takes its last words with it.
# - PIP_NO_CACHE_DIR: the wheel cache is never reused in a layer that is
#   immediately frozen.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies before source, so editing a module does not re-resolve and
# re-download every pin. This layer changes only when requirements.txt does.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# psycopg[binary] ships its own libpq, so no system postgresql-client is
# needed and none is installed. Adding one would be a second, different libpq
# in the image.

COPY sahacore/ ./sahacore/
COPY sql/ ./sql/
COPY tests/ ./tests/
COPY pytest.ini ./

# A non-root user with no home and no shell. The application reads its
# source and writes nothing to disk, so it owns nothing: even a code
# execution bug cannot rewrite the module it came from.
RUN useradd --system --no-create-home --shell /usr/sbin/nologin --uid 10001 sahacore \
    && chown -R root:root /app
USER 10001

EXPOSE 8000

# LIVENESS, NOT READINESS. Docker restarts an unhealthy container, so this
# must be the probe that answers 200 while the process is serving whatever
# the database is doing -- /health, not /health/ready. Wiring the readiness
# probe here would make a database blip restart a healthy container and turn
# a short outage into a crash loop.
#
# Written with urllib rather than curl so no extra package is installed for
# it, and it fails loudly on a non-2xx.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"]

# 0.0.0.0 inside the container only -- `python -m sahacore.api` defaults to
# 127.0.0.1 so running it on a workstation does not expose a port to the
# network by accident. The arguments live here rather than in __main__.py so
# `docker inspect` shows how the process is actually started.
CMD ["uvicorn", "sahacore.api:app", "--host", "0.0.0.0", "--port", "8000"]
