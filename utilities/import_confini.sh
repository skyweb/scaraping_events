#!/bin/bash
# =============================================================================
# Script di importazione confini ISTAT in PostGIS
# Uso: ./import_confini.sh
# Richiede: ogr2ogr (GDAL), docker
# =============================================================================

set -e

# Colori output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="${SCRIPT_DIR}/Limiti01012025"
INFRA_DIR="${SCRIPT_DIR}/../infrastructures"
SQL_FILE="${INFRA_DIR}/config/postgres/init.d/10-comuni-schema.sql"

# Carica variabili da .env
if [ -f "${INFRA_DIR}/.env" ]; then
    export $(grep -E '^POSTGRES_' "${INFRA_DIR}/.env" | xargs)
fi

# Configurazione database (usa .env o valori default)
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-today_events}"
DB_USER="${POSTGRES_USER:-events}"
DB_PASSWORD="${POSTGRES_PASSWORD:-events_secret_2026}"
CONTAINER_NAME="events-postgres"

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Importazione Confini ISTAT 01/01/2025 in PostGIS       ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Database: ${DB_NAME}@${DB_HOST}:${DB_PORT}"
echo "Container: ${CONTAINER_NAME}"
echo ""

# =============================================================================
# Verifiche preliminari
# =============================================================================
echo -e "${YELLOW}[1/5] Verifiche preliminari...${NC}"

# Verifica directory dati
if [ ! -d "$DATA_DIR" ]; then
    echo -e "${RED}Errore: Directory $DATA_DIR non trovata${NC}"
    exit 1
fi
echo "  ✓ Directory dati trovata"

# Verifica file SQL schema
if [ ! -f "$SQL_FILE" ]; then
    echo -e "${RED}Errore: File schema $SQL_FILE non trovato${NC}"
    exit 1
fi
echo "  ✓ File schema SQL trovato"

# Verifica ogr2ogr
if ! command -v ogr2ogr &> /dev/null; then
    echo -e "${RED}Errore: ogr2ogr non trovato${NC}"
    echo "Installa GDAL: brew install gdal"
    exit 1
fi
echo "  ✓ ogr2ogr disponibile"

# Verifica container PostgreSQL
if ! docker ps --filter "name=${CONTAINER_NAME}" --format "{{.Names}}" | grep -q "${CONTAINER_NAME}"; then
    echo -e "${RED}Errore: Container ${CONTAINER_NAME} non in esecuzione${NC}"
    echo "Avvia con: cd infrastructures && docker compose up -d postgres"
    exit 1
fi
echo "  ✓ Container PostgreSQL attivo"

# =============================================================================
# Creazione schema
# =============================================================================
echo ""
echo -e "${YELLOW}[2/5] Creazione schema comuni_italiani...${NC}"

docker exec -i ${CONTAINER_NAME} psql -U ${DB_USER} -d ${DB_NAME} < "${SQL_FILE}"

echo -e "  ${GREEN}✓ Schema creato${NC}"

# =============================================================================
# Importazione shapefile
# =============================================================================
echo ""
echo -e "${YELLOW}[3/5] Importazione shapefile con ogr2ogr...${NC}"

PG_CONN="PG:host=${DB_HOST} port=${DB_PORT} dbname=${DB_NAME} user=${DB_USER} password=${DB_PASSWORD}"

import_shapefile() {
    local shp_path=$1
    local table_name=$2
    local label=$3

    echo -n "  Importando ${label}... "

    ogr2ogr -f "PostgreSQL" "${PG_CONN}" \
        "${DATA_DIR}/${shp_path}" \
        -nln "comuni_italiani.${table_name}" \
        -nlt PROMOTE_TO_MULTI \
        -t_srs EPSG:4326 \
        -lco GEOMETRY_NAME=geom \
        -lco PRECISION=NO \
        -overwrite \
        --config PG_USE_COPY YES \
        2>/dev/null

    echo -e "${GREEN}✓${NC}"
}

import_shapefile "RipGeo01012025/RipGeo01012025_WGS84.shp" "ripartizioni_import" "Ripartizioni (5)"
import_shapefile "Reg01012025/Reg01012025_WGS84.shp" "regioni_import" "Regioni (20)"
import_shapefile "ProvCM01012025/ProvCM01012025_WGS84.shp" "province_import" "Province (107)"
import_shapefile "Com01012025/Com01012025_WGS84.shp" "comuni_import" "Comuni (7896)"

# =============================================================================
# Trasferimento nelle tabelle finali
# =============================================================================
echo ""
echo -e "${YELLOW}[4/5] Trasferimento nelle tabelle finali...${NC}"

docker exec -i ${CONTAINER_NAME} psql -U ${DB_USER} -d ${DB_NAME} << 'EOF'
-- Svuota tabelle finali (nell'ordine corretto per FK)
TRUNCATE comuni_italiani.comuni CASCADE;
TRUNCATE comuni_italiani.province CASCADE;
TRUNCATE comuni_italiani.regioni CASCADE;
TRUNCATE comuni_italiani.ripartizioni CASCADE;

-- Ripartizioni
INSERT INTO comuni_italiani.ripartizioni (cod_rip, den_rip, geom, shape_area, shape_length)
SELECT cod_rip, den_rip, geom, shape_area, shape_leng
FROM comuni_italiani.ripartizioni_import;

-- Regioni
INSERT INTO comuni_italiani.regioni (cod_rip, cod_reg, den_reg, geom, shape_area, shape_length)
SELECT cod_rip, cod_reg, den_reg, geom, shape_area, shape_leng
FROM comuni_italiani.regioni_import;

-- Province
INSERT INTO comuni_italiani.province (cod_rip, cod_reg, cod_prov, cod_cm, cod_uts, den_prov, den_cm, den_uts, sigla, tipo_uts, geom, shape_area, shape_length)
SELECT cod_rip, cod_reg, cod_prov, cod_cm, cod_uts, den_prov, den_cm, den_uts, sigla, tipo_uts, geom, shape_area, shape_leng
FROM comuni_italiani.province_import;

-- Comuni (con calcolo centroide)
INSERT INTO comuni_italiani.comuni (cod_rip, cod_reg, cod_prov, cod_cm, cod_uts, pro_com, pro_com_t, comune, comune_a, cc_uts, geom, centroid, shape_area, shape_length)
SELECT cod_rip, cod_reg, cod_prov, cod_cm, cod_uts, pro_com, pro_com_t, comune, comune_a, cc_uts, geom, ST_Centroid(geom), shape_area, shape_leng
FROM comuni_italiani.comuni_import;

-- Elimina tabelle temporanee
DROP TABLE IF EXISTS comuni_italiani.ripartizioni_import;
DROP TABLE IF EXISTS comuni_italiani.regioni_import;
DROP TABLE IF EXISTS comuni_italiani.province_import;
DROP TABLE IF EXISTS comuni_italiani.comuni_import;
EOF

echo -e "  ${GREEN}✓ Dati trasferiti e tabelle temporanee eliminate${NC}"

# =============================================================================
# Verifica finale
# =============================================================================
echo ""
echo -e "${YELLOW}[5/5] Verifica importazione...${NC}"

docker exec -i ${CONTAINER_NAME} psql -U ${DB_USER} -d ${DB_NAME} << 'EOF'
SELECT
    'ripartizioni' as tabella, COUNT(*) as record FROM comuni_italiani.ripartizioni
UNION ALL SELECT 'regioni', COUNT(*) FROM comuni_italiani.regioni
UNION ALL SELECT 'province', COUNT(*) FROM comuni_italiani.province
UNION ALL SELECT 'comuni', COUNT(*) FROM comuni_italiani.comuni
ORDER BY 1;
EOF

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              Importazione completata!                      ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Query di esempio:"
echo "  docker exec -it ${CONTAINER_NAME} psql -U ${DB_USER} -d ${DB_NAME} -c \\"
echo "    \"SELECT comune FROM comuni_italiani.comuni WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(12.49, 41.89), 4326));\""
