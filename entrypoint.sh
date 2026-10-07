#!/bin/sh
set -e

# Apply DB migrations and gather static files on every start. Both are
# idempotent, so this is safe across restarts.
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Launch gunicorn. PORT defaults to 8007; override via env if needed.
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8007}" \
    --workers "${WEB_CONCURRENCY:-3}" \
    --access-logfile - \
    --error-logfile -
