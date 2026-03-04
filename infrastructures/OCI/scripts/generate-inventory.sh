#!/usr/bin/env bash
# Genera ansible/inventory/hosts.yml dagli output Terraform
#
# Uso: ./scripts/generate-inventory.sh
# Prerequisiti: terraform apply completato
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OCI_DIR="$(dirname "$SCRIPT_DIR")"
TERRAFORM_DIR="$OCI_DIR/terraform"
INVENTORY_FILE="$OCI_DIR/ansible/inventory/hosts.yml"

echo "=== Generazione inventory Ansible ==="

# Verifica che terraform sia disponibile
if ! command -v terraform &>/dev/null; then
    echo "ERRORE: terraform non trovato nel PATH"
    exit 1
fi

# Verifica che lo state esista
if [ ! -f "$TERRAFORM_DIR/terraform.tfstate" ]; then
    echo "ERRORE: terraform.tfstate non trovato in $TERRAFORM_DIR"
    echo "Esegui prima: cd terraform && terraform apply"
    exit 1
fi

cd "$TERRAFORM_DIR"

# Leggi output terraform (JSON array)
echo "Lettura output Terraform..."
NAMES=$(terraform output -json micro_vm_names)
PUBLIC_IPS=$(terraform output -json micro_vm_public_ips)
PRIVATE_IPS=$(terraform output -json micro_vm_private_ips)

# Parse con jq (fallback: Python se jq non disponibile)
if command -v jq &>/dev/null; then
    PARSER="jq"
elif command -v python3 &>/dev/null; then
    PARSER="python3"
else
    echo "ERRORE: serve jq o python3 per il parsing JSON"
    exit 1
fi

get_json_index() {
    local json="$1"
    local index="$2"
    if [ "$PARSER" = "jq" ]; then
        echo "$json" | jq -r ".[$index]"
    else
        echo "$json" | python3 -c "import sys,json; print(json.load(sys.stdin)[$index])"
    fi
}

# Trova indici per nome VM
VM_COUNT=$(echo "$NAMES" | jq -r 'length' 2>/dev/null || echo "$NAMES" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")

MONITOR_IDX=""
CIRUNNER_IDX=""

for ((i=0; i<VM_COUNT; i++)); do
    name=$(get_json_index "$NAMES" "$i")
    case "$name" in
        *monitor*) MONITOR_IDX=$i ;;
        *gw*|*cirunner*|*ci-runner*|*ci_runner*) CIRUNNER_IDX=$i ;;
    esac
done

if [ -z "$MONITOR_IDX" ]; then
    echo "ERRORE: micro VM 'monitor' non trovata negli output terraform"
    echo "Nomi trovati: $NAMES"
    exit 1
fi

MONITOR_PUBLIC=$(get_json_index "$PUBLIC_IPS" "$MONITOR_IDX")
MONITOR_PRIVATE=$(get_json_index "$PRIVATE_IPS" "$MONITOR_IDX")

echo "  micro-monitor:  $MONITOR_PUBLIC (public) / $MONITOR_PRIVATE (private)"

# Genera file inventory
mkdir -p "$(dirname "$INVENTORY_FILE")"

cat > "$INVENTORY_FILE" << YAML
# Auto-generato da generate-inventory.sh - $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# Non committare questo file (e' in .gitignore)
---
all:
  children:
    micro_vms:
      hosts:
        micro-monitor:
          ansible_host: "${MONITOR_PUBLIC}"
          private_ip: "${MONITOR_PRIVATE}"
          ansible_user: opc
          ansible_ssh_private_key_file: "../../oci-key"
YAML

# Aggiungi cirunner se presente
if [ -n "$CIRUNNER_IDX" ]; then
    CIRUNNER_PUBLIC=$(get_json_index "$PUBLIC_IPS" "$CIRUNNER_IDX")
    CIRUNNER_PRIVATE=$(get_json_index "$PRIVATE_IPS" "$CIRUNNER_IDX")
    echo "  micro-gw: $CIRUNNER_PUBLIC (public) / $CIRUNNER_PRIVATE (private)"

    cat >> "$INVENTORY_FILE" << YAML
        micro-gw:
          ansible_host: "${CIRUNNER_PUBLIC}"
          private_ip: "${CIRUNNER_PRIVATE}"
          ansible_user: opc
          ansible_ssh_private_key_file: "../../oci-key"
YAML
fi

# Aggiungi gruppo localhost
cat >> "$INVENTORY_FILE" << 'YAML'

    local:
      hosts:
        localhost:
          ansible_connection: local
          ansible_python_interpreter: "{{ ansible_playbook_python }}"
YAML

echo ""
echo "Inventory generato: $INVENTORY_FILE"
echo ""
echo "Prossimi step:"
echo "  ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/observability-vm-setup.yml"
