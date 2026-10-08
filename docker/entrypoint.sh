#!/bin/sh
# Container entrypoint.
# With no args, serve the API. Any args replace the server command
# (used for one-off tasks such as `alembic upgrade head`).
set -eu

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

# Host networking: this address is the host's. 127.0.0.1 keeps the API
# off the public interface so host Nginx stays the TLS entry point.
BIND_HOST="${BIND_HOST:-127.0.0.1}"
BIND_PORT="${BIND_PORT:-8000}"
WEB_CONCURRENCY="${WEB_CONCURRENCY:-2}"
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-120}"

exec gunicorn app.main:app \
  --workers "${WEB_CONCURRENCY}" \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind "${BIND_HOST}:${BIND_PORT}" \
  --timeout "${GUNICORN_TIMEOUT}" \
  --graceful-timeout 30 \
  --access-logfile - \
  --error-logfile -
