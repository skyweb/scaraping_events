# =============================================================================
# STAGE 1: Build Frontend
# =============================================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# =============================================================================
# STAGE 2: Production Image (Django + Static Frontend)
# =============================================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ .

# Copy built frontend to Django static
COPY --from=frontend-builder /app/frontend/dist /app/staticfiles/frontend

# Create entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
echo "Waiting for database..."\n\
while ! python -c "import psycopg2; psycopg2.connect(host=\"${POSTGRES_HOST:-postgres}\", dbname=\"${POSTGRES_DB}\", user=\"${POSTGRES_USER}\", password=\"${POSTGRES_PASSWORD}\")" 2>/dev/null; do\n\
    sleep 1\n\
done\n\
echo "Database ready!"\n\
\n\
echo "Running migrations..."\n\
python manage.py migrate --noinput\n\
\n\
echo "Collecting static files..."\n\
python manage.py collectstatic --noinput\n\
\n\
echo "Creating superuser if not exists..."\n\
python manage.py shell -c "\n\
from django.contrib.auth import get_user_model;\n\
User = get_user_model();\n\
if not User.objects.filter(username=\"${DJANGO_SUPERUSER_USERNAME:-admin}\").exists():\n\
    User.objects.create_superuser(\"${DJANGO_SUPERUSER_USERNAME:-admin}\", \"${DJANGO_SUPERUSER_EMAIL:-admin@example.com}\", \"${DJANGO_SUPERUSER_PASSWORD:-admin}\");\n\
    print(\"Superuser created\");\n\
else:\n\
    print(\"Superuser already exists\");\n\
"\n\
\n\
exec "$@"\n\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "backoffice.wsgi:application"]
