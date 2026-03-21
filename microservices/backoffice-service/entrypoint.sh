#!/bin/bash
set -e

echo "Waiting for database..."
while ! python -c "import psycopg2; psycopg2.connect(host=\"${POSTGRES_HOST:-postgres}\", dbname=\"${POSTGRES_DB}\", user=\"${POSTGRES_USER}\", password=\"${POSTGRES_PASSWORD}\")" 2>/dev/null; do
    sleep 1
done
echo "Database ready!"

echo "Running migrations..."
python manage.py makemigrations --noinput
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Creating superuser if not exists..."
python manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
if not User.objects.filter(username='${DJANGO_SUPERUSER_USERNAME:-admin}').exists():
    User.objects.create_superuser('${DJANGO_SUPERUSER_USERNAME:-admin}', '${DJANGO_SUPERUSER_EMAIL:-admin@django}', '${DJANGO_SUPERUSER_PASSWORD:-admin}');
    print('Superuser created');
else:
    print('Superuser already exists');
"

exec "$@"
