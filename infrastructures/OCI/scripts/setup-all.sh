#!/bin/bash

set -e

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

echo "=========================================="
echo "  Setup completo cluster OKE"
echo "=========================================="
echo ""

# ── Prerequisiti ─────────────────────────────────────────────
for cmd in ansible-playbook kubectl helm; do
    if ! command -v "$cmd" &> /dev/null; then
        echo "Errore: $cmd non installato!"
        exit 1
    fi
done

if ! kubectl get nodes &> /dev/null; then
    echo "Errore: impossibile connettersi al cluster K8s."
    echo "Esegui prima: ./scripts/deploy.sh oppure ./scripts/get-kubeconfig.sh"
    exit 1
fi
echo "Cluster raggiungibile."
echo ""

if [ ! -f "ansible/vars/oke.yml" ]; then
    echo "Errore: ansible/vars/oke.yml non trovato!"
    echo "Genera con: ./scripts/generate-vars.sh"
    exit 1
fi

# ── Vault password (chiesta una sola volta) ──────────────────
VAULT_PASS_FILE=$(mktemp)
trap 'rm -f "${VAULT_PASS_FILE}"' EXIT

if [ -n "$ANSIBLE_VAULT_PASSWORD_FILE" ] && [ -f "$ANSIBLE_VAULT_PASSWORD_FILE" ]; then
    cp "$ANSIBLE_VAULT_PASSWORD_FILE" "${VAULT_PASS_FILE}"
    echo "Vault password letta da \$ANSIBLE_VAULT_PASSWORD_FILE"
else
    read -r -s -p "Vault password: " VAULT_PASS
    echo ""
    echo "${VAULT_PASS}" > "${VAULT_PASS_FILE}"
    unset VAULT_PASS
fi
chmod 600 "${VAULT_PASS_FILE}"

# Verifica vault password
if ! ansible-vault view ansible/vars/oke-vault.yml --vault-password-file="${VAULT_PASS_FILE}" &> /dev/null; then
    echo "Errore: vault password errata!"
    exit 1
fi
echo "Vault password verificata."
echo ""

ANSIBLE_ARGS="--vault-password-file=${VAULT_PASS_FILE}"

# ── Provisioning micro VM (Python 3.9 per Ansible) ──────────
INVENTORY="ansible/inventory/hosts.yml"
if [ -f "${INVENTORY}" ]; then
    echo "Provisioning micro VM: installazione Python 3.9..."
    MICRO_IPS=$(grep -A1 "micro-" "${INVENTORY}" | grep ansible_host | awk -F'"' '{print $2}')
    SSH_KEY=$(grep ansible_ssh_private_key_file "${INVENTORY}" | head -1 | awk -F'"' '{print $2}')
    for IP in ${MICRO_IPS}; do
        echo "  ${IP}: installazione python39..."
        ssh -i "${SSH_KEY}" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 \
            opc@"${IP}" "sudo dnf install -y python39 > /dev/null 2>&1" && \
            echo "  ${IP}: OK" || echo "  ${IP}: SKIP (non raggiungibile)"
    done
    echo ""
fi

# ── Playbook in ordine ───────────────────────────────────────
PLAYBOOKS=(
    "post-cluster-setup.yml|Infrastruttura base (Traefik, cert-manager, metrics, dashboard)"
    "security-setup.yml|Security (Kyverno)"
    "backup-setup.yml|Backup (Velero)"
    "domain-setup.yml|HTTPS sottodomini (IngressRoute)"
    "reverse-proxy-setup.yml|Reverse proxy (firewalld DNAT)"
    "wireguard-setup.yml|WireGuard VPN (micro-gw)"
)

TOTAL=${#PLAYBOOKS[@]}
CURRENT=0
FAILED=()

for entry in "${PLAYBOOKS[@]}"; do
    PLAYBOOK="${entry%%|*}"
    DESC="${entry##*|}"
    CURRENT=$((CURRENT + 1))
    FILE="ansible/playbooks/${PLAYBOOK}"

    if [ ! -f "${FILE}" ]; then
        echo "[${CURRENT}/${TOTAL}] SKIP ${PLAYBOOK} (file non trovato)"
        continue
    fi

    echo "=========================================="
    echo "[${CURRENT}/${TOTAL}] ${DESC}"
    echo "  -> ${PLAYBOOK}"
    echo "=========================================="

    # Playbook che richiedono inventory micro VM
    EXTRA_ARGS=""
    case "${PLAYBOOK}" in
        observability-vm-setup.yml|reverse-proxy-setup.yml|wireguard-setup.yml)
            if [ -f "${INVENTORY}" ]; then
                EXTRA_ARGS="-i ${INVENTORY}"
            else
                echo "  SKIP: richiede ${INVENTORY} (non trovato)"
                continue
            fi
            ;;
    esac

    if ansible-playbook "${FILE}" ${ANSIBLE_ARGS} ${EXTRA_ARGS}; then
        echo "[${CURRENT}/${TOTAL}] OK ${PLAYBOOK}"
    else
        echo "[${CURRENT}/${TOTAL}] FALLITO ${PLAYBOOK}"
        FAILED+=("${PLAYBOOK}")

        if [ "${CURRENT}" -lt "${TOTAL}" ]; then
            read -r -p "Continuare con il prossimo playbook? (y/n): " cont
            if [ "$cont" != "y" ]; then
                echo "Interrotto dall'utente."
                break
            fi
        fi
    fi
    echo ""
done

# ── Riepilogo ────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "  Riepilogo"
echo "=========================================="

if [ ${#FAILED[@]} -eq 0 ]; then
    echo "  Tutti i playbook completati con successo!"
else
    echo "  Playbook falliti:"
    for f in "${FAILED[@]}"; do
        echo "    - ${f}"
    done
    echo ""
    echo "  Riesegui i falliti singolarmente:"
    for f in "${FAILED[@]}"; do
        echo "    ansible-playbook ansible/playbooks/${f} --ask-vault-pass"
    done
fi
echo ""
