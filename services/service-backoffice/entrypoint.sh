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
    User.objects.create_superuser('${DJANGO_SUPERUSER_USERNAME:-admin}', '${DJANGO_SUPERUSER_EMAIL:-admin@example.com}', '${DJANGO_SUPERUSER_PASSWORD:-admin}');
    print('Superuser created');
else:
    print('Superuser already exists');
"

echo "Creating API user 'api' if not exists..."
python manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
if not User.objects.filter(username='api').exists():
    User.objects.create_user('api', 'api@example.com', 'api');
    print('API user \'api\' created');
else:
    print('API user \'api\' already exists');
"

echo "Creating OAuth2 application 'api demo' if not exists..."
python manage.py shell -c "
from django.contrib.auth import get_user_model;
from oauth2_provider.models import Application;
User = get_user_model();
api_user = User.objects.get(username='api');
if not Application.objects.filter(user=api_user, name='api demo').exists():
    Application.objects.create(
        user=api_user,
        name='api demo',
        client_type='confidential',
        authorization_grant_type='client-credentials'
    );
    print('OAuth2 application \'api demo\' created');
else:
    print('OAuth2 application \'api demo\' already exists');
"

exec "$@"
