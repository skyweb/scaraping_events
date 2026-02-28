#!/bin/bash

set -e

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

echo "=========================================="
echo "  OKE Cluster + Micro VMs Destruction"
echo "=========================================="
echo ""
echo "ATTENZIONE: Verranno distrutte TUTTE le risorse:"
echo "  - Cluster OKE (heavy + light node pool)"
echo "  - 2 Micro VM standalone"
echo "  - VCN, subnet, gateways"
echo ""

if [ ! -t 0 ]; then
    echo "Errore: questo script richiede un terminale interattivo."
    echo "Eseguilo direttamente: ./scripts/destroy.sh"
    exit 1
fi
read -r -p "Sei sicuro di voler distruggere tutto? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Distruzione annullata."
    exit 0
fi

echo ""
echo "Distruzione infrastruttura in corso..."
cd terraform
terraform destroy

echo ""
echo "Pulizia file generati..."
rm -f tfplan

cd "${PROJECT_ROOT}"

echo ""
echo "=========================================="
echo "  Infrastruttura distrutta con successo!"
echo "=========================================="
echo ""
echo "Nota: il kubeconfig potrebbe ancora puntare al cluster."
echo "Pulisci con: kubectl config delete-context <context-name>"
