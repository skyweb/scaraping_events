#!/bin/bash

set -e

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}/terraform"

echo "Recupero kubeconfig dal cluster OKE..."

# Ottieni cluster_id e region dal Terraform output
CLUSTER_ID=$(terraform output -raw cluster_id)
REGION=$(terraform output -raw region)

echo "  Cluster ID: ${CLUSTER_ID}"
echo "  Region: ${REGION}"

# Crea directory .kube se non esiste
mkdir -p "$HOME/.kube"

# Genera kubeconfig
oci ce cluster create-kubeconfig \
    --cluster-id "$CLUSTER_ID" \
    --file "$HOME/.kube/config" \
    --region "$REGION" \
    --token-version 2.0.0 \
    --kube-endpoint PUBLIC_ENDPOINT

echo ""
echo "Kubeconfig salvato in ~/.kube/config"
echo ""

# Verifica connessione
if kubectl cluster-info &> /dev/null; then
    echo "Connessione al cluster OK!"
    kubectl cluster-info
else
    echo "Attenzione: il cluster potrebbe non essere ancora pronto."
    echo "Riprova tra qualche minuto con: kubectl cluster-info"
fi
