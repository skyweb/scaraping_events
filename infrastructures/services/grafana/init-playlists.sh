#!/bin/sh
# =============================================================================
# Grafana init-playlists.sh — Crea playlist per rotazione dashboard su monitor
#
# Eseguito dopo l'avvio di Grafana. Le playlist non supportano provisioning
# via file, quindi vengono create via Grafana HTTP API.
#
# Uso: docker compose exec grafana sh /etc/grafana/init-playlists.sh
# =============================================================================
set -e

GRAFANA_URL="${GRAFANA_URL:-http://localhost:3001}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASS="${GRAFANA_PASS:-admin}"
AUTH="${GRAFANA_USER}:${GRAFANA_PASS}"

echo "Attendo Grafana API..."
until curl -sf -o /dev/null -u "${AUTH}" "${GRAFANA_URL}/api/health"; do
    sleep 2
    echo "  ...attendo"
done
echo "Grafana pronta."

# ---------------------------------------------------------------------------
# Helper: crea o aggiorna playlist
# ---------------------------------------------------------------------------
create_playlist() {
    local name="$1" interval="$2" items="$3"

    # Cerca playlist esistente per nome
    local existing
    existing=$(curl -sf -u "${AUTH}" "${GRAFANA_URL}/api/playlists" \
        | sed 's/},/},\n/g' \
        | grep "\"name\":\"${name}\"" \
        | sed 's/.*"uid":"\([^"]*\)".*/\1/' \
        | head -1)

    local data="{\"name\":\"${name}\",\"interval\":\"${interval}\",\"items\":[${items}]}"

    if [ -n "${existing}" ]; then
        echo "  Aggiorno playlist '${name}' (uid=${existing})..."
        curl -sf -X PUT \
            -u "${AUTH}" \
            -H "Content-Type: application/json" \
            -d "${data}" \
            "${GRAFANA_URL}/api/playlists/${existing}" > /dev/null
    else
        echo "  Creo playlist '${name}'..."
        curl -sf -X POST \
            -u "${AUTH}" \
            -H "Content-Type: application/json" \
            -d "${data}" \
            "${GRAFANA_URL}/api/playlists" > /dev/null
    fi
}

# ---------------------------------------------------------------------------
# Helper: item playlist (dashboard by uid)
# ---------------------------------------------------------------------------
item() {
    echo "{\"type\":\"dashboard_by_uid\",\"value\":\"$1\"}"
}

# ======================= PLAYLISTS ==========================================
echo ""
echo "=== Playlists ==="

# --- API Operations: monitoraggio API consumers e traffico ---
create_playlist "API Operations" "1m" "$(item api-consumers),$(item api-usage),$(item django-prometheus),$(item sla-uptime)"

# --- Infrastructure: salute del sistema ---
create_playlist "Infrastructure" "2m" "$(item services-health),$(item service-detail),$(item redis-exporter),$(item celery-exporter)"

# --- Events Pipeline: flusso dati end-to-end ---
create_playlist "Events Pipeline" "1m" "$(item events-pipeline),$(item business-kpi),$(item airflow-dags),$(item django-logs)"

# --- Security: WAF e autenticazione ---
create_playlist "Security" "2m" "$(item coraza-waf),$(item api-consumers),$(item api-usage)"

# --- Full Overview: tutte le dashboard principali ---
create_playlist "Full Overview" "1m" "$(item services-health),$(item api-consumers),$(item api-usage),$(item events-pipeline),$(item business-kpi),$(item django-prometheus),$(item sla-uptime)"

# ======================= RIEPILOGO ==========================================
echo ""
echo "=== Playlists configurate ==="
curl -sf -u "${AUTH}" "${GRAFANA_URL}/api/playlists" \
    | sed 's/},/},\n/g' | grep -o '"name":"[^"]*"' | sed 's/"name":"//;s/"//' \
    | while read name; do echo "  - ${name}"; done
echo ""
echo "Avvia una playlist: ${GRAFANA_URL}/playlists/play/<uid>?kiosk"
echo "Done."
