#!/bin/bash
# Genera docs/deploy-summary.md con tutti gli output Terraform,
# IP, endpoint, comandi SSH e URL servizi con dominio.
#
# Uso: ./scripts/generate-summary.sh
# Prerequisiti: terraform apply completato

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TERRAFORM_DIR="${PROJECT_ROOT}/terraform"
OUTPUT_FILE="${PROJECT_ROOT}/docs/deploy-summary.md"

cd "${TERRAFORM_DIR}"

# Verifica terraform state
if [ ! -f "terraform.tfstate" ]; then
    echo "Errore: terraform.tfstate non trovato."
    echo "Esegui prima: ./scripts/deploy.sh"
    exit 1
fi

echo "Lettura output Terraform..."

# --- Lettura output ---
CLUSTER_NAME=$(terraform output -raw cluster_name)
CLUSTER_ENDPOINT=$(terraform output -raw cluster_endpoint)
K8S_VERSION=$(terraform output -raw kubernetes_version)
CLUSTER_ID=$(terraform output -raw cluster_id)
REGION=$(terraform output -raw region)
VCN_ID=$(terraform output -raw vcn_id)

OCIR_ENDPOINT=$(terraform output -raw ocir_endpoint)
OCIR_DOCKER_SERVER=$(terraform output -raw ocir_docker_server)
OCIR_USERNAME=$(terraform output -raw ocir_username)
OCIR_NAMESPACE=$(terraform output -raw objectstorage_namespace)

VELERO_BUCKET=$(terraform output -raw velero_bucket_name)
VELERO_S3_ENDPOINT=$(terraform output -raw velero_s3_endpoint)
VELERO_S3_ACCESS_KEY=$(terraform output -raw velero_s3_access_key)

# Micro VM (possono essere 0)
MICRO_VM_COUNT=$(terraform output -json micro_vm_public_ips | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")

# Node pool IDs
HEAVY_POOL_ID=$(terraform output -raw heavy_pool_id)
LIGHT_POOL_ID=$(terraform output -raw light_pool_id)

# Subnet IDs
API_SUBNET_ID=$(terraform output -raw api_subnet_id)
NODE_SUBNET_ID=$(terraform output -raw node_subnet_id)
LB_SUBNET_ID=$(terraform output -raw lb_subnet_id)

# K8s node IPs (se kubectl disponibile)
LIGHT_NODE_IP=""
HEAVY_NODE_IP=""
if command -v kubectl &>/dev/null && kubectl get nodes &>/dev/null 2>&1; then
    LIGHT_NODE_IP=$(kubectl get nodes -l workload=light -o jsonpath='{.items[0].status.addresses[?(@.type=="ExternalIP")].address}' 2>/dev/null || true)
    HEAVY_NODE_IP=$(kubectl get nodes -l workload=heavy -o jsonpath='{.items[0].status.addresses[?(@.type=="ExternalIP")].address}' 2>/dev/null || true)
    # Fallback a InternalIP se ExternalIP non disponibile
    if [ -z "$LIGHT_NODE_IP" ]; then
        LIGHT_NODE_IP=$(kubectl get nodes -l workload=light -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}' 2>/dev/null || true)
    fi
    if [ -z "$HEAVY_NODE_IP" ]; then
        HEAVY_NODE_IP=$(kubectl get nodes -l workload=heavy -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}' 2>/dev/null || true)
    fi
    KUBECTL_NODES=$(kubectl get nodes -o wide --no-headers 2>/dev/null || true)
fi

# OCIR repositories
OCIR_REPOS=$(terraform output -json ocir_repositories | python3 -c "
import sys, json
repos = json.load(sys.stdin)
for name, path in repos.items():
    print(f'| \`{name}\` | \`{path}\` |')
")

# --- Generazione Markdown ---
mkdir -p "$(dirname "${OUTPUT_FILE}")"

TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M UTC")

cat > "${OUTPUT_FILE}" << EOF
# Infrastruttura OCI — Deploy Summary

> Generato il ${TIMESTAMP} da \`./scripts/generate-summary.sh\`

## Cluster OKE

| Parametro | Valore |
|---|---|
| Nome | \`${CLUSTER_NAME}\` |
| Regione | \`${REGION}\` |
| K8s API Endpoint | \`${CLUSTER_ENDPOINT}\` |
| Kubernetes Version | \`${K8S_VERSION}\` |
| Cluster ID | \`${CLUSTER_ID}\` |
| VCN ID | \`${VCN_ID}\` |

### Node Pools

| Pool | OCID |
|---|---|
| heavy (3 OCPU, 18 GB ARM64) | \`${HEAVY_POOL_ID}\` |
| light (1 OCPU, 6 GB ARM64) | \`${LIGHT_POOL_ID}\` |

### Subnet

| Subnet | OCID |
|---|---|
| API Endpoint | \`${API_SUBNET_ID}\` |
| Node | \`${NODE_SUBNET_ID}\` |
| Load Balancer | \`${LB_SUBNET_ID}\` |

EOF

# Nodi K8s (se kubectl disponibile)
if [ -n "$KUBECTL_NODES" ]; then
cat >> "${OUTPUT_FILE}" << EOF
### Nodi K8s

\`\`\`
$(kubectl get nodes -o wide 2>/dev/null)
\`\`\`

| Nodo | IP Pubblico |
|---|---|
| heavy | \`${HEAVY_NODE_IP:-N/A}\` |
| light | \`${LIGHT_NODE_IP:-N/A}\` |

EOF
fi

# Micro VMs
if [ "$MICRO_VM_COUNT" -gt 0 ]; then
    MICRO_NAMES=$(terraform output -json micro_vm_names)
    MICRO_PUBLIC=$(terraform output -json micro_vm_public_ips)
    MICRO_PRIVATE=$(terraform output -json micro_vm_private_ips)

    MICRO_TABLE=$(python3 -c "
import sys, json
names = ${MICRO_NAMES}
pub = ${MICRO_PUBLIC}
priv = ${MICRO_PRIVATE}
for i in range(len(names)):
    print(f'| \`{names[i]}\` | \`{pub[i]}\` | \`{priv[i]}\` | \`ssh -i oci-key opc@{pub[i]}\` |')
")

    # Genera blocchi SSH config
    SSH_CONFIG=$(python3 -c "
import sys, json
names = ${MICRO_NAMES}
pub = ${MICRO_PUBLIC}
for i in range(len(names)):
    print(f'Host {names[i]}')
    print(f'    HostName {pub[i]}')
    print(f'    User opc')
    print(f'    IdentityFile ~/Sites/dev/scaraping_events/infrastructures/OCI/oci-key')
    if i < len(names) - 1:
        print()
")

cat >> "${OUTPUT_FILE}" << EOF
## Micro VMs

| Nome | IP Pubblico | IP Privato | SSH |
|---|---|---|---|
${MICRO_TABLE}

> La chiave privata \`oci-key\` si trova nella root del progetto OCI. Il comando SSH va eseguito dalla directory \`infrastructures/OCI/\`.

<details>
<summary>Tip: configurare ~/.ssh/config per accesso rapido</summary>

Aggiungi al tuo \`~/.ssh/config\`:

\`\`\`
${SSH_CONFIG}
\`\`\`

Poi basta: \`ssh micro-monitor\` o \`ssh micro-gw\`.

</details>

EOF
else
cat >> "${OUTPUT_FILE}" << EOF
## Micro VMs

> Nessuna micro VM creata (\`micro_vm_count = 0\`).

EOF
fi

# OCIR
cat >> "${OUTPUT_FILE}" << EOF
## OCIR (Container Registry)

| Parametro | Valore |
|---|---|
| Endpoint | \`${OCIR_ENDPOINT}\` |
| Docker Server | \`${OCIR_DOCKER_SERVER}\` |
| Username | \`${OCIR_USERNAME}\` |
| Namespace | \`${OCIR_NAMESPACE}\` |

### Repository

| Nome | Full Path |
|---|---|
${OCIR_REPOS}

\`\`\`bash
# Docker login
docker login ${OCIR_ENDPOINT} -u "${OCIR_USERNAME}" -p "<AUTH_TOKEN>"

# Push
docker tag myapp:latest ${OCIR_DOCKER_SERVER}/events/backoffice:latest
docker push ${OCIR_DOCKER_SERVER}/events/backoffice:latest
\`\`\`

### Auth Token

\`\`\`bash
# Se gestito da Terraform (create_ocir_auth_token = true):
cd terraform && terraform output -raw ocir_auth_token
\`\`\`

Se \`create_ocir_auth_token = false\` (quota 2 token raggiunta), il token va recuperato dalla **OCI Console**:

1. **Identity & Security** → **Users** → il tuo utente
2. **Auth Tokens** (menu a sinistra)
3. Copia il token esistente, oppure cancellane uno vecchio e creane uno nuovo

> Il token viene mostrato **solo al momento della creazione**. Se non l'hai salvato, devi generarne uno nuovo (cancellando prima un token per liberare quota).

## Object Storage (Velero Backup)

| Parametro | Valore |
|---|---|
| Bucket | \`${VELERO_BUCKET}\` |
| S3 Endpoint | \`${VELERO_S3_ENDPOINT}\` |
| Access Key | \`${VELERO_S3_ACCESS_KEY}\` |

## Kubeconfig

\`\`\`bash
oci ce cluster create-kubeconfig \\
  --cluster-id ${CLUSTER_ID} \\
  --file \$HOME/.kube/config \\
  --region ${REGION} \\
  --token-version 2.0.0 \\
  --kube-endpoint PUBLIC_ENDPOINT
\`\`\`

EOF

# --- Endpoint servizi (NodePort + Domain) ---
LIGHT_IP="${LIGHT_NODE_IP:-<LIGHT_NODE_IP>}"

# Leggi base_domain e install_reverse_proxy da ansible vars se disponibile
BASE_DOMAIN=""
INSTALL_REVERSE_PROXY=""
VARS_FILE="${PROJECT_ROOT}/ansible/vars/oke.yml"
if [ -f "$VARS_FILE" ]; then
    BASE_DOMAIN=$(grep '^base_domain:' "$VARS_FILE" 2>/dev/null | sed 's/base_domain: *"\(.*\)"/\1/' || true)
    INSTALL_REVERSE_PROXY=$(grep '^install_reverse_proxy:' "$VARS_FILE" 2>/dev/null | sed 's/install_reverse_proxy: *//' || true)
fi

# Micro VM IPs
MONITOR_IP=""
CIRUNNER_IP=""
if [ "$MICRO_VM_COUNT" -gt 0 ]; then
    MONITOR_IP=$(terraform output -json micro_vm_public_ips | python3 -c "import sys,json; print(json.load(sys.stdin)[0])")
    if [ "$MICRO_VM_COUNT" -gt 1 ]; then
        CIRUNNER_IP=$(terraform output -json micro_vm_public_ips | python3 -c "import sys,json; print(json.load(sys.stdin)[1])")
    fi
fi

# IP target per DNS: se reverse proxy, usa micro-gw; altrimenti light node
DNS_TARGET_IP="${LIGHT_IP}"
DNS_TARGET_LABEL="light node"
if [ "$INSTALL_REVERSE_PROXY" = "true" ] && [ -n "$CIRUNNER_IP" ]; then
    DNS_TARGET_IP="${CIRUNNER_IP}"
    DNS_TARGET_LABEL="micro-gw (reverse proxy)"
fi

cat >> "${OUTPUT_FILE}" << EOF
## Endpoint Servizi

### Accesso via NodePort (senza dominio)

| Servizio | URL | Note |
|---|---|---|
| Traefik Dashboard | \`http://${LIGHT_IP}:30090/dashboard/\` | Slash finale obbligatorio |
| Prometheus | \`http://${LIGHT_IP}:31090\` | |
| Alertmanager | \`http://${LIGHT_IP}:31093\` | |
| Loki | \`http://${LIGHT_IP}:31100/ready\` | |
| ArgoCD | \`http://${LIGHT_IP}:30080/argocd/\` | Oppure port-forward :8080 |
| Tekton | \`http://${LIGHT_IP}:30080/tekton/\` | |
| K8s Dashboard | port-forward :8443 | \`kubectl -n monitoring port-forward svc/kubernetes-dashboard-kong-proxy 8443:443\` |
EOF

if [ -n "$MONITOR_IP" ]; then
cat >> "${OUTPUT_FILE}" << EOF
| Grafana | \`http://${MONITOR_IP}:3000\` | Su micro-monitor VM |
EOF
fi

cat >> "${OUTPUT_FILE}" << 'EOF'

### Accesso via dominio (HTTPS — con domain-setup)

> Richiede: `base_domain` configurato in `ansible/vars/oke.yml`, DNS A record, e playbook `domain-setup.yml` eseguito.

EOF

if [ -n "$BASE_DOMAIN" ]; then
    DOMAIN="$BASE_DOMAIN"
else
    DOMAIN="example.com"
fi

cat >> "${OUTPUT_FILE}" << EOF
| Servizio | URL | Target IP | Auth |
|---|---|---|---|
| Traefik Dashboard | \`https://traefik.${DOMAIN}\` | ${DNS_TARGET_LABEL} | OAuth2 Proxy |
| ArgoCD | \`https://argocd.${DOMAIN}\` | ${DNS_TARGET_LABEL} | Nativa (admin) |
| Tekton Dashboard | \`https://tekton.${DOMAIN}\` | ${DNS_TARGET_LABEL} | — |
| Prometheus | \`https://prometheus.${DOMAIN}\` | ${DNS_TARGET_LABEL} | OAuth2 Proxy |
| Alertmanager | \`https://alertmanager.${DOMAIN}\` | ${DNS_TARGET_LABEL} | OAuth2 Proxy |
| Loki | \`https://loki.${DOMAIN}\` | ${DNS_TARGET_LABEL} | OAuth2 Proxy |
| K8s Dashboard | \`https://dashboard.${DOMAIN}\` | ${DNS_TARGET_LABEL} | OAuth2 Proxy |
| OAuth2 Proxy | \`https://auth.${DOMAIN}\` | ${DNS_TARGET_LABEL} | Google callback |
| Grafana | \`https://grafana.${DOMAIN}\` | ${DNS_TARGET_LABEL} | Nativa (admin) |

### DNS A Record da creare

| Sottodominio | IP |
|---|---|
EOF

if [ "$INSTALL_REVERSE_PROXY" = "true" ] && [ -n "$CIRUNNER_IP" ]; then
cat >> "${OUTPUT_FILE}" << EOF
| **TUTTI** (\`traefik\`, \`argocd\`, \`tekton\`, \`prometheus\`, \`alertmanager\`, \`loki\`, \`dashboard\`, \`auth\`, \`grafana\`) | \`${CIRUNNER_IP}\` (micro-gw, reverse proxy) |

> **Reverse Proxy attivo**: micro-gw (IP stabile) inoltra traffico TCP (80/443) a Traefik K8s via firewalld DNAT.
EOF
else
cat >> "${OUTPUT_FILE}" << EOF
| \`traefik\`, \`argocd\`, \`tekton\`, \`prometheus\`, \`alertmanager\`, \`loki\`, \`dashboard\`, \`auth\` | \`${LIGHT_IP}\` (light node) |
EOF

if [ -n "$MONITOR_IP" ]; then
cat >> "${OUTPUT_FILE}" << EOF
| \`grafana\` | \`${MONITOR_IP}\` (micro-monitor VM) |
EOF
fi
fi

# Comandi utili
cat >> "${OUTPUT_FILE}" << 'EOF'

## Comandi Utili

```bash
# Cluster
kubectl get nodes -o wide
kubectl get pods -A
kubectl top nodes

# ArgoCD password
kubectl -n clusters get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d; echo

# K8s Dashboard token
kubectl -n monitoring create token dashboard-admin

# Ansible playbook
./scripts/post-setup.sh                                        # Infrastruttura base
ansible-playbook ansible/playbooks/ci-setup.yml                # CI/CD
ansible-playbook ansible/playbooks/security-setup.yml          # Security
ansible-playbook ansible/playbooks/backup-setup.yml            # Backup
ansible-playbook ansible/playbooks/observability-cluster-setup.yml  # Observability K8s
ansible-playbook ansible/playbooks/domain-setup.yml            # HTTPS sottodomini

# Rigenerare questo file
./scripts/generate-summary.sh
```
EOF

echo ""
echo "Generato: ${OUTPUT_FILE}"
echo ""
