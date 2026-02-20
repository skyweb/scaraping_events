#!/bin/bash
# Script di inizializzazione Apache Superset per Today Events
set -e

echo "=== Inizializzazione Apache Superset ==="

# Crea il database dei metadati Superset se non esiste
echo "Verifica database metadati Superset..."
python << 'PYEOF'
import psycopg2
import os

db_name = os.environ.get("DATABASE_DB", "superset")
conn = psycopg2.connect(
    host=os.environ["DATABASE_HOST"],
    user=os.environ["DATABASE_USER"],
    password=os.environ["DATABASE_PASSWORD"],
    port=int(os.environ.get("DATABASE_PORT", 5432)),
    dbname="postgres",
)
conn.autocommit = True
cur = conn.cursor()
cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
if not cur.fetchone():
    cur.execute(f'CREATE DATABASE "{db_name}"')
    print(f"Database '{db_name}' creato con successo")
else:
    print(f"Database '{db_name}' già esistente")
conn.close()
PYEOF

echo "Aggiornamento schema database..."
superset db upgrade

echo "Creazione utente amministratore..."
superset fab create-admin \
    --username "${SUPERSET_ADMIN_USER:-admin}" \
    --firstname "Admin" \
    --lastname "Superset" \
    --email "${SUPERSET_ADMIN_EMAIL:-admin@superset.local}" \
    --password "${SUPERSET_ADMIN_PASSWORD:-admin}" || echo "Utente già esistente, continuazione..."

echo "Inizializzazione ruoli e permessi..."
superset init

# Importa assets pre-configurati (database, dataset, chart, dashboard) se presenti.
# La connessione al DB Today Events è definita in assets/databases/Today_Events.yaml.
# Se non ci sono assets, crea la connessione via CLI come fallback.
if [ -d "/app/assets" ] && [ "$(ls -A /app/assets 2>/dev/null)" ]; then
    echo "Importazione assets (database, dataset, chart, dashboard)..."
    superset import-directory --overwrite /app/assets/ \
        || echo "Attenzione: importazione assets fallita o già importati, continuazione..."
else
    echo "Nessun asset trovato, configurazione connessione Today Events via CLI..."
    superset set_database_uri \
        --database-name "Today Events" \
        --uri "postgresql+psycopg2://${DATABASE_USER}:${DATABASE_PASSWORD}@${DATABASE_HOST}:${DATABASE_PORT:-5432}/${EVENTS_DB_NAME:-today_events}" \
        || echo "Connessione già esistente o errore non bloccante, continuazione..."
fi

echo "=== Superset pronto! Accedi su http://localhost:8088 ==="
