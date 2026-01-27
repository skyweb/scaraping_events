#!/bin/bash
set -e

# Entrypoint per eseguire gli spider
# Utilizzo:
#   ./entrypoint.sh city_today milano roma --periodo=questa-settimana
#   ./entrypoint.sh zero_eu milano bologna
#   ./entrypoint.sh city_today --help

SOURCE=$1
shift

if [ -z "$SOURCE" ]; then
    echo "Utilizzo: entrypoint.sh <source> [città...] [--periodo=PERIODO]"
    echo ""
    echo "Sources disponibili:"
    echo "  - city_today"
    echo "  - zero_eu"
    exit 1
fi

case $SOURCE in
    city_today)
        cd /app/city_today
        python run_spider.py "$@"
        # Copia output nella directory condivisa se esiste
        if [ -d "/data/output" ]; then
            cp -f /app/city_today/output/*.json /data/output/ 2>/dev/null || true
        fi
        ;;
    zero_eu)
        cd /app/zero_eu
        python run_spider.py "$@"
        # Copia output nella directory condivisa se esiste
        if [ -d "/data/output" ]; then
            cp -f /app/zero_eu/output/*.json /data/output/ 2>/dev/null || true
        fi
        ;;
    *)
        echo "Source non valida: $SOURCE"
        echo "Sources disponibili: city_today, zero_eu"
        exit 1
        ;;
esac
