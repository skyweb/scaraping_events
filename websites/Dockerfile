FROM python:3.11-slim

LABEL maintainer="Today Events"
LABEL description="Scrapy spiders for events scraping"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy spider projects
COPY city_today /app/city_today
COPY zero_eu /app/zero_eu

# Create output directories
RUN mkdir -p /app/city_today/output /app/zero_eu/output /data/output

# Copy entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command (show help)
CMD ["--help"]
