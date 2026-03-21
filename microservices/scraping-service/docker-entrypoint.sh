#!/bin/sh
# =============================================================================
# Entrypoint per il container Events Scraper
# =============================================================================
#
# Modalità di utilizzo:
#
# 1. Avvia Scrapyd server (default):
#    docker run -d -p 6800:6800 events-scraper
#
# 2. Esegui spider direttamente:
#    docker run --rm events-scraper scrapy crawl city_today -a cities=milano
#
# 3. Shell interattiva:
#    docker run -it --rm events-scraper bash
#

set -e

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    printf "${GREEN}[INFO]${NC} %s\n" "$1"
}

log_warn() {
    printf "${YELLOW}[WARN]${NC} %s\n" "$1"
}

log_error() {
    printf "${RED}[ERROR]${NC} %s\n" "$1"
}

# Deploy progetto su Scrapyd se non già presente
deploy_project() {
    if [ -f "/app/scrapy.cfg" ]; then
        log_info "Verifico deploy progetto su Scrapyd..."

        # Attendi che Scrapyd sia pronto
        i=0; while [ $i -lt 10 ]; do i=$((i+1))
            if curl -s http://localhost:6800/daemonstatus.json > /dev/null 2>&1; then
                break
            fi
            sleep 1
        done

        # Deploy del progetto
        cd /app
        if scrapyd-deploy 2>/dev/null; then
            log_info "Progetto deployato con successo"
        else
            log_warn "Deploy fallito o progetto già presente"
        fi
    fi
}

# Mostra help
show_help() {
    cat << EOF
Events Scraper - Spider per eventi italiani

UTILIZZO:
  docker run [OPTIONS] events-scraper [COMMAND]

COMANDI:
  scrapyd              Avvia Scrapyd server (default)
  scrapy crawl <spider> [args]   Esegui spider direttamente
  bash                 Shell interattiva
  help                 Mostra questo messaggio

SPIDER DISPONIBILI:
  zero_eu      Eventi da zero.eu
  city_today   Eventi da *Today.it (50+ città)
  artribune    Eventi culturali da artribune.com

ESEMPI:
  # Avvia Scrapyd
  docker run -d -p 6800:6800 events-scraper

  # Scraping Milano
  docker run --rm events-scraper scrapy crawl city_today -a cities=milano -o /data/milano.json

  # Scraping multiple città
  docker run --rm events-scraper scrapy crawl city_today -a cities=milano,roma -a periodo=weekend

  # Con Scrapyd API
  curl http://localhost:6800/schedule.json \\
    -d project=events_scraper \\
    -d spider=city_today \\
    -d cities=milano

VARIABILI D'AMBIENTE:
  POSTGRES_HOST      Host PostgreSQL (default: localhost)
  POSTGRES_PORT      Porta PostgreSQL (default: 5432)
  POSTGRES_DB        Database (default: events)
  POSTGRES_USER      Utente (default: postgres)
  POSTGRES_PASSWORD  Password (default: postgres)
  SCRAPY_LOG_LEVEL   Livello log (default: INFO)

EOF
}

# Main
case "${1:-scrapyd}" in
    scrapyd)
        log_info "Avvio Scrapyd server..."
        log_info "Dashboard: http://localhost:6800"
        log_info "API docs: http://localhost:6800/listprojects.json"

        # Avvia Scrapyd in background per il deploy
        scrapyd &
        SCRAPYD_PID=$!

        # Attendi e deploya
        sleep 3
        deploy_project

        # Riporta Scrapyd in foreground
        wait $SCRAPYD_PID
        ;;

    scrapy)
        log_info "Esecuzione spider..."
        shift
        exec scrapy "$@"
        ;;

    help|--help|-h)
        show_help
        ;;

    bash|sh)
        exec /bin/sh
        ;;

    *)
        # Comando generico
        exec "$@"
        ;;
esac
