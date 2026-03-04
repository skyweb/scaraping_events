#!/bin/bash

set -e

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

# --- Configurazione retry per "Out of host capacity" ---
RETRY_INTERVAL=${RETRY_INTERVAL:-300}   # secondi tra i tentativi (default: 5 minuti)
MAX_RETRIES=${MAX_RETRIES:-288}         # tentativi massimi (default: 288 = 24 ore con intervallo 5 min)

echo "=========================================="
echo "  OKE Cluster + Micro VMs Deployment"
echo "=========================================="
echo ""

# Check prerequisites
if [ ! -f "terraform/terraform.tfvars" ]; then
    echo "Errore: terraform/terraform.tfvars non trovato!"
    echo "Copia terraform/terraform.tfvars.example e configuralo."
    exit 1
fi

for cmd in terraform oci kubectl; do
    if ! command -v "$cmd" &> /dev/null; then
        echo "Errore: $cmd non installato!"
        exit 1
    fi
done

# Step 1: Terraform init
echo "Step 1: Inizializzazione Terraform..."
cd terraform
terraform init

# Step 2: Plan
echo ""
echo "Step 2: Piano infrastruttura..."
terraform plan -out=tfplan

echo ""
if [ ! -t 0 ]; then
    echo "Errore: questo script richiede un terminale interattivo."
    echo "Eseguilo direttamente: ./scripts/deploy.sh"
    rm -f tfplan
    exit 1
fi
read -r -p "Vuoi applicare questo piano? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Deploy annullato."
    rm -f tfplan
    exit 0
fi

# Step 3: Apply (con retry automatico per "Out of host capacity")
echo ""
echo "Step 3: Applicazione Terraform (15-20 minuti per OKE)..."
echo "  Se 'Out of host capacity': retry ogni ${RETRY_INTERVAL}s (max ${MAX_RETRIES} tentativi)"
echo ""

ATTEMPT=0
while true; do
    ATTEMPT=$((ATTEMPT + 1))

    # Prima esecuzione usa il piano salvato, i retry usano apply diretto
    if [ "$ATTEMPT" -eq 1 ] && [ -f tfplan ]; then
        set +e
        terraform apply tfplan 2>&1 | tee /tmp/tf-apply-output.log
        TF_EXIT=${PIPESTATUS[0]}
        set -e
        rm -f tfplan
    else
        set +e
        terraform apply -auto-approve 2>&1 | tee /tmp/tf-apply-output.log
        TF_EXIT=${PIPESTATUS[0]}
        set -e
    fi

    # Successo
    if [ "$TF_EXIT" -eq 0 ]; then
        echo ""
        echo "Terraform apply completato con successo!"
        [ "$ATTEMPT" -gt 1 ] && echo "  (riuscito al tentativo #${ATTEMPT})"
        break
    fi

    # Controlla se l'errore e' "Out of host capacity"
    if grep -qi "Out of host capacity" /tmp/tf-apply-output.log; then
        if [ "$ATTEMPT" -ge "$MAX_RETRIES" ]; then
            echo ""
            echo "Errore: 'Out of host capacity' dopo ${MAX_RETRIES} tentativi."
            echo "La regione non ha capacita' disponibile. Riprova piu' tardi."
            rm -f /tmp/tf-apply-output.log
            exit 1
        fi

        NEXT_TIME=$(date -v+${RETRY_INTERVAL}S +"%H:%M:%S" 2>/dev/null || date -d "+${RETRY_INTERVAL} seconds" +"%H:%M:%S" 2>/dev/null || echo "~$(( RETRY_INTERVAL / 60 )) min")
        echo ""
        echo "  [${ATTEMPT}/${MAX_RETRIES}] Out of host capacity — prossimo tentativo alle ${NEXT_TIME} (tra ${RETRY_INTERVAL}s)..."
        sleep "$RETRY_INTERVAL"
    else
        # Errore diverso da capacity: fallisci subito
        echo ""
        echo "Errore Terraform (non legato a capacity). Controlla l'output sopra."
        rm -f /tmp/tf-apply-output.log
        exit 1
    fi
done
rm -f /tmp/tf-apply-output.log

# Step 4: Get kubeconfig
echo ""
echo "Step 4: Configurazione kubeconfig..."
cd "${PROJECT_ROOT}"
./scripts/get-kubeconfig.sh

# Step 5: Wait for nodes
echo ""
echo "Step 5: Attesa nodi OKE Ready..."
echo "  (i nodi impiegano 5-10 minuti dopo il cluster)"
TIMEOUT=600
ELAPSED=0
while true; do
    READY=$(kubectl get nodes --no-headers 2>/dev/null | grep -c " Ready" || true)
    if [ "$READY" -ge 2 ]; then
        echo "  2 nodi Ready!"
        break
    fi
    if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
        echo "  Timeout: solo $READY nodi Ready dopo ${TIMEOUT}s"
        echo "  Controlla con: kubectl get nodes"
        break
    fi
    echo "  $READY/2 nodi Ready... (${ELAPSED}s)"
    sleep 30
    ELAPSED=$((ELAPSED + 30))
done

# Step 6: Show cluster info
echo ""
echo "Step 6: Verifica cluster..."
kubectl get nodes -o wide
echo ""
kubectl get nodes --show-labels | grep workload || true

# Summary
echo ""
echo "=========================================="
echo "  Infrastruttura OCI pronta!"
echo "=========================================="
echo ""
cd terraform
echo "Cluster: $(terraform output -raw cluster_name)"
echo "Endpoint: $(terraform output -raw cluster_endpoint)"
echo "K8s version: $(terraform output -raw kubernetes_version)"
echo ""
echo "Micro VMs:"
terraform output ssh_micro_commands 2>/dev/null || true
echo ""
echo "Comandi utili:"
echo "  kubectl get nodes"
echo "  kubectl get pods -A"
echo "  kubectl get ns"
echo ""
# Genera summary markdown
cd "${PROJECT_ROOT}"
./scripts/generate-summary.sh

echo "Prossimo step — configurazione cluster con Ansible:"
echo "  ./scripts/post-setup.sh"
echo ""
