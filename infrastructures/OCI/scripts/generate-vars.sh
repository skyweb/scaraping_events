#!/usr/bin/env bash
# Genera ansible/vars/oke.yml (config) e ansible/vars/oke-vault.yml (secret)
# dagli output Terraform
#
# Uso: ./scripts/generate-vars.sh
# Prerequisiti: terraform apply completato
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OCI_DIR="$(dirname "$SCRIPT_DIR")"
TERRAFORM_DIR="$OCI_DIR/terraform"
VARS_FILE="$OCI_DIR/ansible/vars/oke.yml"
VAULT_FILE="$OCI_DIR/ansible/vars/oke-vault.yml"

echo "=== Generazione ansible/vars/oke.yml + oke-vault.yml ==="

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

# Verifica jq o python3 per parsing JSON
if command -v jq &>/dev/null; then
    PARSER="jq"
elif command -v python3 &>/dev/null; then
    PARSER="python3"
else
    echo "ERRORE: serve jq o python3 per il parsing JSON"
    exit 1
fi

cd "$TERRAFORM_DIR"

# --- Lettura output Terraform ---
echo "Lettura output Terraform..."

REGION=$(terraform output -raw region)
TENANCY_OCID=$(terraform output -raw tenancy_ocid)
OCIR_ENDPOINT=$(terraform output -raw ocir_endpoint)
OCIR_NAMESPACE=$(terraform output -raw objectstorage_namespace)
OCIR_USERNAME=$(terraform output -raw ocir_username)
OCIR_AUTH_TOKEN=$(terraform output -raw ocir_auth_token)
VELERO_BUCKET=$(terraform output -raw velero_bucket_name)
VELERO_S3_URL=$(terraform output -raw velero_s3_endpoint)
VELERO_ACCESS_KEY=$(terraform output -raw velero_s3_access_key)
VELERO_SECRET_KEY=$(terraform output -raw velero_s3_secret_key)

# Estrai email dall'ocir_username (namespace/email → email)
OCIR_EMAIL="${OCIR_USERNAME#*/}"

echo "  region:         $REGION"
echo "  ocir_endpoint:  $OCIR_ENDPOINT"
echo "  ocir_namespace: $OCIR_NAMESPACE"
echo "  ocir_username:  $OCIR_USERNAME"

# --- k8s_node_ip (tentativo kubectl) ---
K8S_NODE_IP="K8S_NODE_PRIVATE_IP"
if command -v kubectl &>/dev/null; then
    echo "Tentativo lettura IP nodo light da kubectl..."
    NODE_IP=$(kubectl get nodes -l workload=light -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}' 2>/dev/null || true)
    if [ -n "$NODE_IP" ]; then
        K8S_NODE_IP="$NODE_IP"
        echo "  k8s_node_ip:    $K8S_NODE_IP (da kubectl)"
    else
        echo "  k8s_node_ip:    placeholder (kubectl non ha trovato nodi light)"
    fi
else
    echo "  k8s_node_ip:    placeholder (kubectl non disponibile)"
fi

# --- Generazione file ---
mkdir -p "$(dirname "$VARS_FILE")"

# =====================================================================
# oke.yml — configurazione non-sensibile
# =====================================================================
cat > "$VARS_FILE" << YAML
# Auto-generato da generate-vars.sh - $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# Non committare questo file (e' in .gitignore)
#
# Configurazione non-sensibile — i secret sono in oke-vault.yml (criptato)
# Valori infrastrutturali compilati automaticamente da Terraform output.
---

# OCIR (Oracle Container Registry) - per imagePullSecret Kubernetes
ocir_region: "${REGION}"
ocir_endpoint: "${OCIR_ENDPOINT}"
ocir_namespace: "${OCIR_NAMESPACE}"
ocir_username: "${OCIR_USERNAME}"
# ocir_auth_token -> in oke-vault.yml

# Namespaces da creare nel cluster
namespaces:
  - events
  - monitoring
  - traefik
  - cert-manager
  - argocd
  - tekton-pipelines
  - velero
  - kyverno

# Traefik Ingress Controller
install_traefik: true
traefik_http_nodeport: 30080
traefik_https_nodeport: 30443
traefik_dashboard_nodeport: 30090

# ArgoCD (GitOps)
install_argocd: true

# Tekton Pipelines + Kaniko (CI/CD cloud-native)
install_tekton: true
tekton_version: "v0.65.2"
tekton_dashboard_version: "v0.46.0"

# cert-manager
install_cert_manager: true
cert_manager_version: "v1.17.2"
letsencrypt_email: "${OCIR_EMAIL}"

# metrics-server
install_metrics_server: true

# Kubernetes Dashboard
install_dashboard: true

# Kyverno (Policy Engine - Security)
install_kyverno: true
kyverno_enforcement_mode: "Audit"
kyverno_excluded_namespaces:
  - kube-system
  - kyverno
  - traefik
  - cert-manager
  - monitoring
  - argocd
  - tekton-pipelines
  - velero

# =============================================================================
# Observability - Cluster (K8s)
# =============================================================================

# Prometheus (prometheus-community/prometheus)
install_prometheus: true
prometheus_nodeport: 31090
prometheus_retention: "7d"
prometheus_storage_size: "10Gi"
prometheus_server_cpu_limit: "500m"
prometheus_server_memory_limit: "512Mi"

# Alertmanager (gestione alert e notifiche)
install_alertmanager: true
alertmanager_nodeport: 31093
alertmanager_cpu_limit: "100m"
alertmanager_memory_limit: "128Mi"

# Loki (grafana/loki) - SingleBinary mode
install_loki: true
loki_nodeport: 31100
loki_retention_period: "168h"  # 7 giorni
loki_cpu_limit: "250m"
loki_memory_limit: "256Mi"

# Promtail (grafana/promtail) - DaemonSet log shipper
install_promtail: true
promtail_cpu_limit: "100m"
promtail_memory_limit: "64Mi"

# OpenTelemetry Collector (open-telemetry/opentelemetry-collector) - DaemonSet
install_otel_collector: true
otel_otlp_grpc_nodeport: 31317
otel_cpu_limit: "200m"
otel_memory_limit: "128Mi"

# Jaeger (jaegertracing/jaeger) - Tracing UI
install_jaeger: true
jaeger_nodeport: 31686
jaeger_cpu_limit: "500m"
jaeger_memory_limit: "512Mi"

# Redis Exporter (metriche Prometheus per Redis)
install_redis_exporter: false    # false fino a deploy app su K8s
redis_exporter_cpu_limit: "50m"
redis_exporter_memory_limit: "64Mi"
redis_k8s_host: "redis://redis.events.svc:6379"
# redis_k8s_password -> in oke-vault.yml

# Celery Exporter (metriche Prometheus per Celery)
install_celery_exporter: false   # false fino a deploy app su K8s
celery_exporter_cpu_limit: "50m"
celery_exporter_memory_limit: "64Mi"
# celery_broker_url -> in oke-vault.yml

# =============================================================================
# Observability - Grafana su Micro VM
# =============================================================================

install_grafana_vm: true
grafana_version: "11.4.0"
# grafana_admin_password -> in oke-vault.yml
grafana_port: 3000
install_grafana_dashboards: true
install_grafana_alerting: true

# IP privato di un nodo K8s (per datasource Grafana -> Prometheus/Loki via NodePort)
k8s_node_ip: "${K8S_NODE_IP}"

# OCI Monitoring (Grafana plugin oci-metrics-datasource + oci-logs-datasource)
install_oci_datasources: true
oci_tenancy_ocid: "${TENANCY_OCID}"
oci_region: "${REGION}"

# =============================================================================
# Backup & Disaster Recovery
# =============================================================================

install_velero: true
velero_bucket_name: "${VELERO_BUCKET}"
velero_s3_region: "${REGION}"
velero_s3_url: "${VELERO_S3_URL}"
# velero_aws_access_key_id -> in oke-vault.yml
# velero_aws_secret_access_key -> in oke-vault.yml
velero_backup_schedule: "0 2 * * *"  # ogni notte alle 02:00
velero_backup_ttl: "168h"            # retention 7 giorni

# =============================================================================
# Domain Setup (HTTPS via sottodomini)
# =============================================================================
# Decommentare e configurare per abilitare routing HTTPS via sottodomini.
# Richiede: DNS A record per ogni sottodominio -> IP pubblico corretto.
#
# Servizi K8s -> A record -> IP pubblico del nodo light (K8s)
# Grafana     -> A record -> IP pubblico della micro-monitor VM

# base_domain: "example.com"

# Sottodomini (default se non specificati)
# traefik_subdomain: "traefik"        # traefik.example.com   -> Traefik Dashboard
# argocd_subdomain: "argocd"          # argocd.example.com    -> ArgoCD
# tekton_subdomain: "tekton"          # tekton.example.com    -> Tekton Dashboard
# prometheus_subdomain: "prometheus"  # prometheus.example.com -> Prometheus
# alertmanager_subdomain: "alertmanager"  # alertmanager.example.com -> Alertmanager
# loki_subdomain: "loki"              # loki.example.com      -> Loki
# dashboard_subdomain: "dashboard"    # dashboard.example.com -> K8s Dashboard
# grafana_subdomain: "grafana"        # grafana.example.com   -> Grafana (Caddy su micro VM)
# jaeger_subdomain: "jaeger"          # jaeger.example.com    -> Jaeger UI
# auth_subdomain: "auth"              # auth.example.com      -> OAuth2 Proxy callback

# --- Autenticazione servizi senza auth nativa ---
# Scegliere UNA delle due opzioni: BasicAuth OPPURE OAuth2 Proxy (Google SSO)
# I secret (basicauth_users, oauth2_proxy_*) vanno in oke-vault.yml

# Opzione A: BasicAuth — configurare basicauth_users in oke-vault.yml

# Opzione B: OAuth2 Proxy (Google SSO)
# install_oauth2_proxy: false
# oauth2_proxy_allowed_emails:
#   - "your.email@gmail.com"
# I secret (client_id, client_secret, cookie_secret) -> in oke-vault.yml
YAML

echo ""
echo "Generato: $VARS_FILE"

# =====================================================================
# oke-vault.yml — secret e credenziali (da criptare con ansible-vault)
# =====================================================================
cat > "$VAULT_FILE" << YAML
# Auto-generato da generate-vars.sh - $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# CRIPTARE con: ansible-vault encrypt ansible/vars/oke-vault.yml
# EDITARE con:  ansible-vault edit ansible/vars/oke-vault.yml
---

# OCIR (Oracle Container Registry)
ocir_auth_token: "${OCIR_AUTH_TOKEN}"

# Grafana
grafana_admin_password: "CHANGE_ME"   # <-- CAMBIA QUESTA PASSWORD

# Velero (Backup)
velero_aws_access_key_id: "${VELERO_ACCESS_KEY}"
velero_aws_secret_access_key: "${VELERO_SECRET_KEY}"

# Redis (password per Redis Exporter e Celery broker)
redis_k8s_password: "CHANGE_ME"
celery_broker_url: "redis://:CHANGE_ME@redis.events.svc:6379/0"

# BasicAuth (Opzione A -- decommentare se si usa BasicAuth)
# basicauth_users: "admin:\$\$2y\$\$05\$\$HASH_HERE"

# OAuth2 Proxy (Opzione B -- decommentare se si usa Google SSO)
# oauth2_proxy_client_id: "YOUR_CLIENT_ID.apps.googleusercontent.com"
# oauth2_proxy_client_secret: "YOUR_CLIENT_SECRET"
# oauth2_proxy_cookie_secret: "YOUR_COOKIE_SECRET"
YAML

echo "Generato: $VAULT_FILE"

# --- Offri cifratura automatica ---
echo ""
if command -v ansible-vault &>/dev/null; then
    echo "Vuoi criptare oke-vault.yml ora? (richiede una password)"
    read -rp "Criptare con ansible-vault? [y/N] " ENCRYPT
    if [[ "$ENCRYPT" == "y" || "$ENCRYPT" == "Y" ]]; then
        ansible-vault encrypt "$VAULT_FILE"
        echo "File criptato. Usa --ask-vault-pass per eseguire i playbook."
    else
        echo "ATTENZIONE: oke-vault.yml contiene secret in chiaro."
        echo "Criptare manualmente con: ansible-vault encrypt $VAULT_FILE"
    fi
else
    echo "ATTENZIONE: ansible-vault non trovato. Criptare manualmente:"
    echo "  ansible-vault encrypt $VAULT_FILE"
fi

echo ""
echo "TODO:"
echo "  1. Cambia grafana_admin_password in oke-vault.yml"
echo "  2. Cambia redis_k8s_password e celery_broker_url in oke-vault.yml"
if [ "$K8S_NODE_IP" = "K8S_NODE_PRIVATE_IP" ]; then
    echo "  3. Imposta k8s_node_ip in oke.yml con: kubectl get nodes -l workload=light -o wide"
fi
echo ""
echo "Prossimi step:"
echo "  ansible-playbook ansible/playbooks/post-cluster-setup.yml --ask-vault-pass"
