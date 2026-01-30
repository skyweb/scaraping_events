#!/bin/bash
# =============================================================================
# Script di importazione dati aggiuntivi comuni da comuni-json
# Aggiunge: codice_catastale, cap[], popolazione
# Uso: ./import_comuni_json.sh
# =============================================================================

set -e

# Colori output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
JSON_FILE="${SCRIPT_DIR}/comuni-json/comuni.json"
INFRA_DIR="${SCRIPT_DIR}/../infrastructures"
SQL_FILE="${INFRA_DIR}/config/postgres/init.d/11-comuni-extra-columns.sql"

# Carica variabili da .env
if [ -f "${INFRA_DIR}/.env" ]; then
    export $(grep -E '^POSTGRES_' "${INFRA_DIR}/.env" | xargs)
fi

# Configurazione database
DB_NAME="${POSTGRES_DB:-today_events}"
DB_USER="${POSTGRES_USER:-events}"
CONTAINER_NAME="events-postgres"

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Importazione dati aggiuntivi comuni (CAP, pop, etc)    ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# =============================================================================
# Verifiche preliminari
# =============================================================================
echo -e "${YELLOW}[1/5] Verifiche preliminari...${NC}"

if [ ! -f "$JSON_FILE" ]; then
    echo -e "${RED}Errore: File $JSON_FILE non trovato${NC}"
    exit 1
fi
echo "  ✓ File comuni.json trovato"

if [ ! -f "$SQL_FILE" ]; then
    echo -e "${RED}Errore: File schema $SQL_FILE non trovato${NC}"
    exit 1
fi
echo "  ✓ File schema SQL trovato"

if ! docker ps --filter "name=${CONTAINER_NAME}" --format "{{.Names}}" | grep -q "${CONTAINER_NAME}"; then
    echo -e "${RED}Errore: Container ${CONTAINER_NAME} non in esecuzione${NC}"
    exit 1
fi
echo "  ✓ Container PostgreSQL attivo"

# =============================================================================
# Aggiunta colonne
# =============================================================================
echo ""
echo -e "${YELLOW}[2/5] Aggiunta colonne alla tabella comuni...${NC}"

docker exec -i ${CONTAINER_NAME} psql -U ${DB_USER} -d ${DB_NAME} < "${SQL_FILE}" 2>/dev/null

echo -e "  ${GREEN}✓ Colonne aggiunte${NC}"

# =============================================================================
# Generazione CSV per import
# =============================================================================
echo ""
echo -e "${YELLOW}[3/5] Conversione JSON -> CSV...${NC}"

# Crea CSV temporaneo usando Python
python3 << PYEOF
import json
import csv
import sys

with open('${JSON_FILE}', 'r', encoding='utf-8') as f:
    comuni = json.load(f)

with open('/tmp/comuni_extra.csv', 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['codice', 'nome', 'codice_catastale', 'cap', 'popolazione'])

    for c in comuni:
        # Converti array CAP in formato PostgreSQL: {val1,val2}
        cap_pg = '{' + ','.join(c.get('cap', [])) + '}'
        writer.writerow([
            c.get('codice', ''),
            c.get('nome', ''),
            c.get('codiceCatastale', ''),
            cap_pg,
            c.get('popolazione', 0)
        ])

print(f"  Processati {len(comuni)} comuni")
PYEOF

echo -e "  ${GREEN}✓ CSV generato${NC}"

# =============================================================================
# Import nella staging table
# =============================================================================
echo ""
echo -e "${YELLOW}[4/5] Import dati in staging table...${NC}"

# Copia il CSV nel container
docker cp /tmp/comuni_extra.csv ${CONTAINER_NAME}:/tmp/comuni_extra.csv

# Import con COPY
docker exec -i ${CONTAINER_NAME} psql -U ${DB_USER} -d ${DB_NAME} << 'EOF'
-- Svuota staging
TRUNCATE comuni_italiani.comuni_json_staging;

-- Import CSV
COPY comuni_italiani.comuni_json_staging(codice, nome, codice_catastale, cap, popolazione)
FROM '/tmp/comuni_extra.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

-- Conta record importati
SELECT COUNT(*) as "Record importati in staging" FROM comuni_italiani.comuni_json_staging;
EOF

echo -e "  ${GREEN}✓ Dati importati in staging${NC}"

# =============================================================================
# Update tabella comuni
# =============================================================================
echo ""
echo -e "${YELLOW}[5/5] Aggiornamento tabella comuni...${NC}"

docker exec -i ${CONTAINER_NAME} psql -U ${DB_USER} -d ${DB_NAME} << 'EOF'
-- Update comuni esistenti
UPDATE comuni_italiani.comuni c
SET
    codice_catastale = s.codice_catastale,
    cap = s.cap,
    popolazione = s.popolazione
FROM comuni_italiani.comuni_json_staging s
WHERE c.pro_com_t = s.codice;

-- Conta aggiornamenti
SELECT COUNT(*) as "Comuni aggiornati"
FROM comuni_italiani.comuni
WHERE codice_catastale IS NOT NULL;

-- Comuni ISTAT 2025 non trovati nel JSON 2020 (fusioni recenti)
SELECT 'Comuni senza dati CAP (nuovi/fusi dopo 2020):' as info;
SELECT pro_com_t, comune
FROM comuni_italiani.comuni
WHERE codice_catastale IS NULL
ORDER BY comune
LIMIT 20;

-- Cleanup
DROP TABLE IF EXISTS comuni_italiani.comuni_json_staging;
EOF

# Cleanup locale
rm -f /tmp/comuni_extra.csv
docker exec ${CONTAINER_NAME} rm -f /tmp/comuni_extra.csv 2>/dev/null || true

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              Importazione completata!                      ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Query di esempio:"
echo "  -- Trova CAP di un comune"
echo "  SELECT comune, cap FROM comuni_italiani.comuni WHERE comune ILIKE 'roma';"
echo ""
echo "  -- Comuni più popolosi"
echo "  SELECT comune, popolazione FROM comuni_italiani.comuni ORDER BY popolazione DESC LIMIT 10;"
