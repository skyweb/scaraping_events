# =============================================================================
# Scraping Comuni Italiani - Dockerfile
# =============================================================================
# Esegue lo spider per scaricare dati su regioni, province e comuni
# da comuni-italiani.it e genera 3 file JSON in /data/output/

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OUTPUT_DIR=/data/output

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scrapy.cfg .
COPY comuni_istat/ comuni_istat/

RUN mkdir -p /data/output

VOLUME /data/output

CMD ["scrapy", "crawl", "comuni_spider"]
