# OCI Infrastructure - OKE + Micro VMs

Cluster Kubernetes gestito (OKE) + 2 micro VM standalone su Oracle Cloud Free Tier.

## Architettura

```
┌─────────────────────────────────────────────────────────┐
│  OCI Free Tier                                          │
│                                                         │
│  ┌─── OKE Cluster (BASIC_CLUSTER - free) ────────────┐  │
│  │                                                    │  │
│  │  heavy-pool (A1.Flex ARM64)                        │  │
│  │  3 OCPU │ 18 GB RAM │ 120 GB boot                 │  │
│  │  → DB, backoffice, Celery, APISIX, Keycloak        │  │
│  │                                                    │  │
│  │  light-pool (A1.Flex ARM64)                        │  │
│  │  1 OCPU │ 6 GB RAM │ 40 GB boot                   │  │
│  │  → etcd, Loki, Tempo, Alertmanager, servizi light  │  │
│  │                                                    │  │
│  └────────────────────────────────────────────────────┘  │
│                                                         │
│  ┌─── Micro VMs (E2.1.Micro AMD x86_64) ────────────┐  │
│  │                                                    │  │
│  │  micro-monitor  (1/8 OCPU, 1 GB, 50 GB)           │  │
│  │  → Healthcheck, monitoring esterno                 │  │
│  │                                                    │  │
│  │  micro-gw  (1/8 OCPU, 1 GB, 50 GB)                │  │
│  │  → Reverse proxy (firewalld DNAT → APISIX K8s)     │  │
│  │                                                    │  │
│  └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Risorse Free Tier

| Risorsa | Allocazione | Limite Free |
|---|---|---|
| OCPU A1.Flex | 3 + 1 = 4 | 4 |
| RAM A1.Flex | 18 + 6 = 24 GB | 24 GB |
| Micro VM (E2.1.Micro) | 2 istanze | 2 |
| Boot Volume | 120 + 40 + 50 + 50 = 260 GB | 200 GB* |
| Object Storage | 1 bucket (Velero backup) | 20 GB Standard |
| OCIR | 2 repository privati | Free (usa Object Storage) |
| OKE Control Plane | BASIC_CLUSTER | Free |

## Rete

```
VCN 10.0.0.0/16 (oke-vcn)
├── API Endpoint Subnet  10.0.0.0/28   (public) - K8s API :6443
├── Node Subnet          10.0.1.0/24   (public) - Worker nodes
├── LB Subnet            10.0.2.0/24   (public) - HTTP/HTTPS
└── Micro VM Subnet      10.0.3.0/28   (public) - VM standalone
```

Flannel CNI (pods: 10.244.0.0/16, services: 10.96.0.0/16).

## Stack Servizi

Allineato al `docker-compose.dev.yml` locale:

| Servizio | Immagine | Namespace | Nodo |
|---|---|---|---|
| **PostgreSQL 16 + PostGIS** | imresamu/postgis:16-3.4 | database | heavy |
| **Redis 7** | redis:7-alpine | database | heavy |
| **Django Backoffice** | OCIR custom | apps | heavy |
| **Celery Worker** | OCIR custom | database | heavy |
| **Celery Beat** | OCIR custom | database | heavy |
| **APISIX 3.15** | apache/apisix:3.15.0-ubuntu | apps | heavy |
| **APISIX Dashboard** | apache/apisix-dashboard:3.0.1-alpine | apps | heavy |
| **etcd** | coreos/etcd | apps | light |
| **Keycloak 26** | keycloak/keycloak:26.0 | apps | heavy |
| **Airflow 2.9** | apache/airflow:2.9.2 | airflow | heavy |
| **MinIO** | minio/minio | database | heavy |
| **Harbor Registry** | goharbor/harbor-helm | devs | heavy |
| **Prometheus** | prometheus-community/prometheus | monitoring | heavy |
| **Grafana 12.3** | grafana/grafana | monitoring | heavy |
| **Loki 3.6** | grafana/loki | monitoring | light |
| **Alloy 1.14** | grafana/alloy | monitoring | tutti (DaemonSet) |
| **Tempo 2.9** | grafana/tempo | monitoring | light |
| **OTel Collector** | otel/opentelemetry-collector-contrib | monitoring | tutti (DaemonSet) |
| **Redis Exporter** | oliver006/redis_exporter | database | light |
| **Celery Exporter** | danihodovic/celery-exporter | database | light |
| **PostgreSQL Exporter** | prometheus-postgres-exporter | monitoring | light |
| **ArgoCD** | argo/argo-cd | clusters | light |
| **Tekton** | tekton-pipelines | tekton | - |
| **Velero** | velero/velero | clusters | light |

## Flusso di rete

```
Client (HTTPS)
    ↓
micro-gw (firewalld DNAT :443 → NodePort 30443)
    ↓
APISIX Gateway (TLS termination, OIDC SSO via Keycloak)
    ├→ backoffice.${DOMAIN}  → Django (apps:8000)
    ├→ grafana.${DOMAIN}     → Grafana (monitoring:3001)
    ├→ airflow.${DOMAIN}     → Airflow (airflow:8080)
    ├→ auth.${DOMAIN}        → Keycloak (apps:8080)
    ├→ registry.${DOMAIN}    → Harbor (devs:80)
    ├→ minio.${DOMAIN}       → MinIO Console (database:9001)
    └→ ...
```

## Quick Start

```bash
# 1. Genera chiavi SSH
./scripts/generate-ssh-key.sh

# 2. Configura terraform.tfvars
cp terraform/terraform.tfvars.example terraform/terraform.tfvars

# 3. Provisioning infrastruttura (~15-20 min)
./scripts/deploy.sh

# 4. Genera variabili Ansible da Terraform output
./scripts/generate-vars.sh
./scripts/generate-inventory.sh

# 5. Setup completo (tutti i playbook in sequenza)
./scripts/setup-all.sh
```

## Playbook Ansible

Eseguibili singolarmente con `ansible-playbook ansible/playbooks/<nome>.yml --ask-vault-pass`.

| # | Playbook | Descrizione |
|---|---|---|
| 1 | `post-cluster-setup.yml` | Namespace, cert-manager, metrics-server, K8s Dashboard |
| 2 | `database-setup.yml` | PostgreSQL + Redis (Secret, StatefulSet) |
| 3 | `monitoring-setup.yml` | Prometheus, Grafana, Loki, Alloy, Tempo, OTEL Collector |
| 4 | `apisix-keycloak-setup.yml` | APISIX Gateway + Keycloak (OIDC SSO) |
| 5 | `apps-setup.yml` | Django Backoffice + Celery |
| 6 | `minio-setup.yml` | MinIO Object Storage |
| 7 | `airflow-setup.yml` | Apache Airflow (webserver + scheduler) |
| 8 | `scraping-setup.yml` | Pod templates per spider Scrapy |
| 9 | `harbor-setup.yml` | Harbor Docker Registry |
| 10 | `linkerd-setup.yml` | Linkerd Service Mesh (opzionale) |
| 11 | `ci-setup.yml` | ArgoCD + Tekton (GitOps + CI/CD) |
| 12 | `backup-setup.yml` | Velero (backup su OCI Object Storage) |
| 13 | `security-setup.yml` | Kyverno Policy Engine (opzionale) |
| 14 | `reverse-proxy-setup.yml` | firewalld DNAT su micro-gw |
| 15 | `wireguard-setup.yml` | WireGuard VPN su micro-gw |

### Playbook rimossi (obsoleti)

| Playbook | Motivo |
|---|---|
| `traefik-setup.yml` | Sostituito da APISIX (gateway unico) |
| `domain-setup.yml` | Routing gestito da APISIX route, non più IngressRoute |
| `backstage-setup.yml` | Non più necessario nello stack |

## Observability

```
App (OTLP) → OTel Collector → Tempo (traces)
                             → Prometheus (spanmetrics)

App (Prometheus endpoint) → Prometheus scrape → Grafana

Container log → Alloy (DaemonSet) → Loki → Grafana
```

### Prometheus scrape jobs

| Job | Target |
|---|---|
| `otel-spanmetrics` | `otel-collector...monitoring.svc:8889` |
| `django` | `backoffice.apps.svc:8000` |
| `redis-exporter` | `redis-exporter.database.svc:9121` |
| `celery-exporter` | `celery-exporter.database.svc:9808` |
| `apisix` | `apisix-gateway.apps.svc:9091` |
| `keycloak` | `keycloak.apps.svc:8080` |
| `postgres-exporter` | `postgres-exporter...monitoring.svc:80` |
| `alloy` | `alloy.monitoring.svc:12345` |
| `kubelet-cadvisor` | Auto-discovery nodi |

## Configurazione

Ogni servizio è attivabile/disattivabile in `ansible/vars/oke.yml`:

```yaml
install_cert_manager: true
install_metrics_server: true
install_dashboard: true
install_grafana: true
install_tempo: true
install_harbor: true
install_airflow: true
install_scraping: true
install_minio: true
install_keycloak: true
install_apisix: true
install_argocd: true
install_tekton: true
install_linkerd: true
install_kyverno: false
install_velero: true
install_reverse_proxy: true
install_wireguard: true
```

## Struttura

```
OCI/
├── terraform/          # Provisioning OCI (VCN, OKE, micro VM, OCIR, Object Storage)
├── ansible/
│   ├── playbooks/      # 15 playbook (uno per servizio/gruppo)
│   ├── vars/           # oke.yml + oke-vault.yml (secrets criptati)
│   └── inventory/      # hosts.yml (micro VM, auto-generato)
├── k8s/                # Manifest Kubernetes per namespace
│   ├── monitoring/     # Helm values (Prometheus, Grafana, Loki, Alloy, Tempo, OTEL)
│   ├── apisix/         # Helm values (APISIX + etcd + dashboard)
│   ├── keycloak/       # Helm values + realm ConfigMap
│   ├── airflow/        # Deployment (webserver, scheduler, init)
│   ├── events-backoffice/  # Deployment Django
│   ├── postgres/       # StatefulSet PostgreSQL
│   ├── redis/          # Deployment Redis + exporter + Celery
│   ├── minio/          # Deployment MinIO
│   ├── harbor/         # Helm values Harbor
│   ├── velero/         # Helm values Velero + UI
│   ├── tekton/         # Pipeline + Task (Kaniko build)
│   ├── scraping/       # ConfigMap + RBAC per KubernetesPodOperator
│   └── wireguard/      # Deployment WireGuard
├── scripts/            # Automazione (deploy, destroy, generate-vars, setup-all)
└── docs/               # Summary generati
```
