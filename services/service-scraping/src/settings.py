# -*- coding: utf-8 -*-
"""
Configurazione Scrapy per Events Scraper.

Tutte le impostazioni possono essere sovrascritte tramite variabili d'ambiente
con il prefisso SCRAPY_ (es: SCRAPY_LOG_LEVEL=DEBUG).

Per configurazioni specifiche per spider, usare custom_settings nello spider.
"""

import os

# =============================================================================
# CONFIGURAZIONE BASE
# =============================================================================

BOT_NAME = "events_scraper"
SPIDER_MODULES = ["spiders"]
NEWSPIDER_MODULE = "spiders"

# =============================================================================
# IDENTIFICAZIONE
# =============================================================================

# User-Agent realistico per evitare blocchi
USER_AGENT = os.getenv(
    "SCRAPY_USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Rispetta robots.txt (può essere disabilitato per spider specifici)
ROBOTSTXT_OBEY = os.getenv("SCRAPY_ROBOTSTXT_OBEY", "True").lower() == "true"

# =============================================================================
# THROTTLING E CONCORRENZA
# =============================================================================

# Numero massimo di richieste concorrenti
CONCURRENT_REQUESTS = int(os.getenv("SCRAPY_CONCURRENT_REQUESTS", "8"))

# Richieste concorrenti per dominio
CONCURRENT_REQUESTS_PER_DOMAIN = int(
    os.getenv("SCRAPY_CONCURRENT_REQUESTS_PER_DOMAIN", "2")
)

# Delay tra richieste (secondi)
DOWNLOAD_DELAY = float(os.getenv("SCRAPY_DOWNLOAD_DELAY", "1.0"))

# =============================================================================
# AUTOTHROTTLE (throttling automatico)
# =============================================================================

AUTOTHROTTLE_ENABLED = os.getenv("SCRAPY_AUTOTHROTTLE_ENABLED", "True").lower() == "true"
AUTOTHROTTLE_START_DELAY = float(os.getenv("SCRAPY_AUTOTHROTTLE_START_DELAY", "1.0"))
AUTOTHROTTLE_MAX_DELAY = float(os.getenv("SCRAPY_AUTOTHROTTLE_MAX_DELAY", "10.0"))
AUTOTHROTTLE_TARGET_CONCURRENCY = float(
    os.getenv("SCRAPY_AUTOTHROTTLE_TARGET_CONCURRENCY", "2.0")
)
AUTOTHROTTLE_DEBUG = os.getenv("SCRAPY_AUTOTHROTTLE_DEBUG", "False").lower() == "true"

# =============================================================================
# RETRY E TIMEOUT
# =============================================================================

# Timeout download (secondi)
DOWNLOAD_TIMEOUT = int(os.getenv("SCRAPY_DOWNLOAD_TIMEOUT", "30"))

# Retry
RETRY_ENABLED = True
RETRY_TIMES = int(os.getenv("SCRAPY_RETRY_TIMES", "3"))
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# =============================================================================
# MIDDLEWARE
# =============================================================================

DOWNLOADER_MIDDLEWARES = {
    # Middleware personalizzati (se necessari)
    # "events_scraper.middlewares.CustomMiddleware": 543,
}

SPIDER_MIDDLEWARES = {
    # Middleware spider personalizzati
}

# =============================================================================
# PIPELINE
# =============================================================================

ITEM_PIPELINES = {
    # Validazione e pulizia dati
    "pipelines.ValidationPipeline": 100,
    # Generazione hash per deduplicazione
    "pipelines.HashGeneratorPipeline": 200,
    # === SCEGLI UNA DELLE SEGUENTI OPZIONI ===
    # Opzione 1: Salvataggio diretto su PostgreSQL
    # "pipelines.PostgresPipeline": 300,
    # Opzione 2: Invio tramite API al backoffice (raccomandato)
    # "pipelines.ApiPipeline": 300,
}

# =============================================================================
# DATABASE POSTGRESQL (per PostgresPipeline)
# =============================================================================

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "events")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

# =============================================================================
# API INGESTION (per ApiPipeline)
# =============================================================================

# URL base del backoffice API
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# Credenziali OAuth2 (client_credentials grant)
API_CLIENT_ID = os.getenv("API_CLIENT_ID", "")
API_CLIENT_SECRET = os.getenv("API_CLIENT_SECRET", "")

# Configurazione batch
API_BATCH_SIZE = int(os.getenv("API_BATCH_SIZE", "50"))
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))

# =============================================================================
# OUTPUT E FEED
# =============================================================================

# Encoding output
FEED_EXPORT_ENCODING = "utf-8"

# Formato feed di default
FEED_FORMAT = os.getenv("SCRAPY_FEED_FORMAT", "json")

# Directory output (relativa a src/)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.getenv("SCRAPY_OUTPUT_DIR", os.path.join(_BASE_DIR, "data"))

# =============================================================================
# LOGGING
# =============================================================================

LOG_LEVEL = os.getenv("SCRAPY_LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
LOG_DATEFORMAT = "%Y-%m-%d %H:%M:%S"

# Log su file (opzionale)
LOG_FILE = os.getenv("SCRAPY_LOG_FILE", None)

# =============================================================================
# CACHE HTTP (per development)
# =============================================================================

HTTPCACHE_ENABLED = os.getenv("SCRAPY_HTTPCACHE_ENABLED", "False").lower() == "true"
HTTPCACHE_EXPIRATION_SECS = int(os.getenv("SCRAPY_HTTPCACHE_EXPIRATION_SECS", "86400"))
HTTPCACHE_DIR = os.getenv("SCRAPY_HTTPCACHE_DIR", "httpcache")

# =============================================================================
# TELNET CONSOLE
# =============================================================================

# Disabilitato per sicurezza in produzione
TELNETCONSOLE_ENABLED = os.getenv("SCRAPY_TELNETCONSOLE_ENABLED", "False").lower() == "true"

# =============================================================================
# SCRAPYD
# =============================================================================

# Queste impostazioni sono usate quando il progetto viene deployato su Scrapyd
SCRAPYD_URL = os.getenv("SCRAPYD_URL", "http://localhost:6800")
