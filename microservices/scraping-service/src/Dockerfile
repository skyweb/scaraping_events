# =============================================================================
# Events Scraper - Immagine Docker con Scrapyd
# =============================================================================
#
# Build:
#   docker build -t events-scraper .
#
# Run Scrapyd server:
#   docker run -d -p 6800:6800 --name scrapyd events-scraper
#
# Run spider direttamente:
#   docker run --rm events-scraper scrapy crawl city_today -a cities=milano -o /data/output.json
#

FROM python:3.11-slim

LABEL maintainer="Events Scraping Team"
LABEL description="Scrapy spiders for events scraping with Scrapyd"
LABEL version="1.0.0"

# Variabili d'ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Directory di lavoro
WORKDIR /app

# Installa dipendenze di sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copia requirements e installa dipendenze Python
# NB: paths relativi al build context (services/service-scraping/)
COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Crea directory per Scrapyd
RUN mkdir -p /var/lib/scrapyd/eggs \
             /var/lib/scrapyd/logs \
             /var/lib/scrapyd/dbs \
             /data/output

# Copia il progetto Scrapy (src/ = events_scraper package)
COPY src/ /app/events_scraper/
COPY src/scrapy.cfg /app/scrapy.cfg
COPY src/scrapyd.conf /etc/scrapyd/scrapyd.conf

# Copia script di avvio
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Deploy automatico del progetto su Scrapyd all'avvio
# Il progetto viene deployato come egg
RUN cd /app && scrapyd-deploy --build-egg=/var/lib/scrapyd/eggs/events_scraper.egg 2>/dev/null || true

# Porta Scrapyd
EXPOSE 6800

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:6800/daemonstatus.json || exit 1

# Volume per output e logs
VOLUME ["/data/output", "/var/lib/scrapyd/logs"]

# Entrypoint
ENTRYPOINT ["docker-entrypoint.sh"]

# Comando default: avvia Scrapyd
CMD ["scrapyd"]
