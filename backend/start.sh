#!/bin/sh
# Production entrypoint: migrate, (re)seed demo presets, start gunicorn.
set -e
python manage.py migrate --noinput
python manage.py seed_presets
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --threads 4 \
  --timeout 90 \
  --access-logfile -
