#!/bin/bash

# Script per elencare le istanze compute OCI e il loro stato
# Mostra stato, IP, shape, OCPU, RAM per ogni istanza nel compartment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "==========================================="
echo "  OCI Compute Instances — Status"
echo "==========================================="
echo ""

# --- Verifica OCI CLI ---
if ! command -v oci &> /dev/null; then
    echo "❌ Errore: OCI CLI non trovato."
    echo ""
    echo "Installa OCI CLI:"
    echo "  macOS: brew install oci-cli"
    echo "  Linux: bash -c \"\$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)\""
    echo ""
    exit 1
fi

if [ ! -f ~/.oci/config ]; then
    echo "❌ Errore: OCI CLI non configurato (~/.oci/config mancante)."
    echo "Esegui: oci setup config"
    exit 1
fi

echo "✅ OCI CLI configurato"
echo ""

# --- Profilo OCI ---
OCI_PROFILE="${OCI_PROFILE:-DEFAULT}"

# --- Compartment OCID ---
# 1. Prova dal terraform.tfvars
# 2. Altrimenti chiede all'utente
COMPARTMENT_OCID=""

TFVARS_FILE="${PROJECT_ROOT}/terraform/terraform.tfvars"
if [ -f "${TFVARS_FILE}" ]; then
    COMPARTMENT_OCID=$(grep "^compartment_ocid" "${TFVARS_FILE}" | cut -d'"' -f2)
fi

if [ -z "${COMPARTMENT_OCID}" ]; then
    echo "⚠️  Compartment OCID non trovato in terraform.tfvars"
    echo ""
    echo "Compartment disponibili:"
    oci iam compartment list \
        --all \
        --compartment-id-in-subtree true \
        --access-level ACCESSIBLE \
        --profile "${OCI_PROFILE}" \
        --query "data[?\"lifecycle-state\" == 'ACTIVE'].{Name:name, OCID:id}" \
        --output table 2>/dev/null || true
    echo ""
    read -p "Inserisci il Compartment OCID: " COMPARTMENT_OCID
fi

echo "📋 Compartment: ${COMPARTMENT_OCID}"
echo ""

# --- Query istanze ---
echo "🔍 Recupero istanze compute..."
echo ""

# Recupera tutte le istanze (non TERMINATED) in formato JSON
INSTANCES_JSON=$(oci compute instance list \
    --compartment-id "${COMPARTMENT_OCID}" \
    --profile "${OCI_PROFILE}" \
    --query "data[?\"lifecycle-state\" != 'TERMINATED'].{
        name:\"display-name\",
        state:\"lifecycle-state\",
        shape:shape,
        ocpus:\"shape-config\".ocpus,
        ram_gb:\"shape-config\".\"memory-in-gbs\",
        time_created:\"time-created\",
        id:id,
        ad:\"availability-domain\"
    }" \
    --output json 2>/dev/null)

# Controlla se ci sono istanze
INSTANCE_COUNT=$(echo "${INSTANCES_JSON}" | jq 'length')

if [ "${INSTANCE_COUNT}" -eq 0 ] 2>/dev/null || [ -z "${INSTANCES_JSON}" ] || [ "${INSTANCES_JSON}" = "null" ]; then
    echo "ℹ️  Nessuna istanza attiva trovata nel compartment."
    echo ""
    echo "Per creare le istanze:"
    echo "  cd ${PROJECT_ROOT} && ./scripts/deploy.sh"
    exit 0
fi

echo "=========================================="
printf "  %-28s %-12s %-22s %6s %6s\n" "NOME" "STATO" "SHAPE" "OCPU" "RAM"
echo "=========================================="

# Itera le istanze e stampa una riga per ciascuna
echo "${INSTANCES_JSON}" | jq -r '.[] | "\(.name)|\(.state)|\(.shape)|\(.ocpus)|\(.ram_gb)"' | while IFS='|' read -r NAME STATE SHAPE OCPUS RAM; do
    # Icona stato
    case "${STATE}" in
        RUNNING)  ICON="🟢" ;;
        STOPPED)  ICON="🔴" ;;
        STARTING) ICON="🟡" ;;
        STOPPING) ICON="🟡" ;;
        *)        ICON="⚪" ;;
    esac

    printf "  %-28s %s %-10s %-22s %5s %5sG\n" "${NAME}" "${ICON}" "${STATE}" "${SHAPE}" "${OCPUS}" "${RAM}"
done

echo "=========================================="
echo ""

# --- Dettagli IP (solo per istanze RUNNING) ---
RUNNING_IDS=$(echo "${INSTANCES_JSON}" | jq -r '.[] | select(.state == "RUNNING") | .id')

if [ -n "${RUNNING_IDS}" ]; then
    echo "📡 IP delle istanze RUNNING:"
    echo ""
    printf "  %-28s %-18s %-18s\n" "NOME" "IP PUBBLICO" "IP PRIVATO"
    echo "  -----------------------------------------------------------"

    echo "${INSTANCES_JSON}" | jq -r '.[] | select(.state == "RUNNING") | "\(.id)|\(.name)"' | while IFS='|' read -r ID NAME; do
        # Recupera VNIC attachments per l'istanza
        VNIC_JSON=$(oci compute vnic-attachment list \
            --compartment-id "${COMPARTMENT_OCID}" \
            --instance-id "${ID}" \
            --profile "${OCI_PROFILE}" \
            --query "data[0].\"vnic-id\"" \
            --raw-output 2>/dev/null)

        if [ -n "${VNIC_JSON}" ] && [ "${VNIC_JSON}" != "null" ]; then
            VNIC_DETAILS=$(oci network vnic get \
                --vnic-id "${VNIC_JSON}" \
                --profile "${OCI_PROFILE}" \
                --query "data.{pub:\"public-ip\", priv:\"private-ip\"}" \
                --output json 2>/dev/null)

            PUBLIC_IP=$(echo "${VNIC_DETAILS}" | jq -r '.pub // "N/A"')
            PRIVATE_IP=$(echo "${VNIC_DETAILS}" | jq -r '.priv // "N/A"')
        else
            PUBLIC_IP="N/A"
            PRIVATE_IP="N/A"
        fi

        printf "  %-28s %-18s %-18s\n" "${NAME}" "${PUBLIC_IP}" "${PRIVATE_IP}"
    done

    echo ""
fi

# --- Riepilogo risorse ---
TOTAL_OCPUS=$(echo "${INSTANCES_JSON}" | jq '[.[].ocpus] | add')
TOTAL_RAM=$(echo "${INSTANCES_JSON}" | jq '[.[].ram_gb] | add')
RUNNING_COUNT=$(echo "${INSTANCES_JSON}" | jq '[.[] | select(.state == "RUNNING")] | length')

echo "=========================================="
echo "  Riepilogo"
echo "=========================================="
echo "  Istanze totali:    ${INSTANCE_COUNT}"
echo "  Istanze running:   ${RUNNING_COUNT}"
echo "  OCPU totali:       ${TOTAL_OCPUS}"
echo "  RAM totale:        ${TOTAL_RAM} GB"
echo ""

# --- Comandi utili ---
if [ "${RUNNING_COUNT}" -gt 0 ]; then
    echo "📝 Comandi utili:"
    echo ""

    # SSH per ogni istanza RUNNING (utente opc, chiave oci-key)
    echo "${INSTANCES_JSON}" | jq -r '.[] | select(.state == "RUNNING") | "\(.id)|\(.name)"' | while IFS='|' read -r ID NAME; do
        VNIC_ID=$(oci compute vnic-attachment list \
            --compartment-id "${COMPARTMENT_OCID}" \
            --instance-id "${ID}" \
            --profile "${OCI_PROFILE}" \
            --query "data[0].\"vnic-id\"" \
            --raw-output 2>/dev/null)

        if [ -n "${VNIC_ID}" ] && [ "${VNIC_ID}" != "null" ]; then
            IP=$(oci network vnic get \
                --vnic-id "${VNIC_ID}" \
                --profile "${OCI_PROFILE}" \
                --query "data.\"public-ip\"" \
                --raw-output 2>/dev/null)

            if [ -n "${IP}" ] && [ "${IP}" != "null" ]; then
                echo "  SSH ${NAME}:  ssh -i oci-key opc@${IP}"
            fi
        fi
    done

    echo ""
    echo "  Cluster K8s:           kubectl get nodes -o wide"
    echo "  Pod status:            kubectl get pods -A"
    echo "  Risorse nodi:          kubectl top nodes"
    echo "  IngressRoute:          kubectl get ingressroute -A"
    echo ""
fi
