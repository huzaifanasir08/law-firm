#!/bin/sh
set -e

echo "Waiting for PostgreSQL to be ready..."
while ! nc -z ${POSTGRES_HOST:-db} ${POSTGRES_PORT:-5432}; do
  sleep 0.5
done
echo "PostgreSQL is ready!"

echo "Running migrations..."
python manage.py migrate --noinput

echo "Creating superuser if needed..."
python manage.py create_superuser

echo "Collecting static files..."
python manage.py collectstatic --noinput --clear || true

echo "Starting Gunicorn server..."
exec gunicorn project.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --threads 2 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -
