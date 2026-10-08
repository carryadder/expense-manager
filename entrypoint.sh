#!/bin/sh
set -e

# Apply DB migrations and gather static files on every start. Both are
# idempotent, so this is safe across restarts.
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Launch gunicorn. PORT defaults to 8007; override via env if needed.
#
# Use threaded (gthread) workers rather than the default sync worker: an idle
# keep-alive/probe connection holds a sync worker hostage and the master kills
# it after --timeout with "WORKER TIMEOUT (no URI read)". Threads let a worker
# juggle many connections, so idle sockets no longer exhaust the pool.
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8007}" \
    --worker-class gthread \
    --workers "${WEB_CONCURRENCY:-3}" \
    --threads "${GUNICORN_THREADS:-4}" \
    --timeout "${GUNICORN_TIMEOUT:-60}" \
    --graceful-timeout 30 \
    --keep-alive 5 \
    --access-logfile - \
    --error-logfile -
