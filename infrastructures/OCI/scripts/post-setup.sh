#!/bin/bash

set -e

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

echo "=========================================="
echo "  Ansible Post-Cluster Setup"
echo "=========================================="
echo ""

# Check prerequisites
if ! command -v ansible-playbook &> /dev/null; then
    echo "Errore: ansible-playbook non installato!"
    echo "Installa con: pip install ansible"
    exit 1
fi

if ! command -v kubectl &> /dev/null; then
    echo "Errore: kubectl non installato!"
    exit 1
fi

# Verify cluster connectivity
echo "Verifica connessione al cluster..."
if ! kubectl get nodes &> /dev/null; then
    echo "Errore: impossibile connettersi al cluster K8s."
    echo "Esegui prima: ./scripts/deploy.sh oppure ./scripts/get-kubeconfig.sh"
    exit 1
fi
echo "  Cluster raggiungibile."
echo ""

# Check vars file
if [ ! -f "ansible/vars/oke.yml" ]; then
    echo "Errore: ansible/vars/oke.yml non trovato!"
    echo ""
    echo "Opzioni:"
    echo "  1. Genera automaticamente da Terraform: ./scripts/generate-vars.sh"
    echo "  2. Copia manualmente: cp ansible/vars/oke.yml.example ansible/vars/oke.yml"
    exit 1
fi

# Run playbook
echo "Esecuzione post-cluster-setup.yml..."
echo ""
ansible-playbook ansible/playbooks/post-cluster-setup.yml "$@"

echo ""
echo "=========================================="
echo "  Post-setup completato!"
echo "=========================================="
echo ""
echo "Playbook opzionali disponibili:"
echo "  ansible-playbook ansible/playbooks/ci-setup.yml              # CI/CD (ArgoCD + Tekton)"
echo "  ansible-playbook ansible/playbooks/security-setup.yml        # Security (Kyverno)"
echo "  ansible-playbook ansible/playbooks/backup-setup.yml          # Backup (Velero)"
echo "  ansible-playbook ansible/playbooks/observability-cluster-setup.yml  # Observability K8s"
echo "  ansible-playbook ansible/playbooks/domain-setup.yml          # HTTPS sottodomini"
echo ""