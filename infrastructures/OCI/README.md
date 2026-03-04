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
│  │  → DB, backoffice, Celery, workers                 │  │
│  │                                                    │  │
│  │  light-pool (A1.Flex ARM64)                        │  │
│  │  1 OCPU │ 6 GB RAM │ 40 GB boot                   │  │
│  │  → NGINX Ingress, servizi leggeri                  │  │
│  │                                                    │  │
│  └────────────────────────────────────────────────────┘  │
│                                                         │
│  ┌─── Micro VMs (E2.1.Micro AMD x86_64) ────────────┐  │
│  │                                                    │  │
│  │  micro-monitor  (1/8 OCPU, 1 GB, 50 GB)           │  │
│  │  → Uptime Kuma, healthcheck, reverse proxy         │  │
│  │                                                    │  │
│  │  micro-gw (1/8 OCPU, 1 GB, 50 GB)           │  │
│  │  → CI runner leggero, task minimali                │  │
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

> *Boot volume: il free tier include 2x 50 GB (per le 2 micro VM) + i boot volume dei nodi OKE sono inclusi nelle risorse A1. I nodi OKE con boot volume > 50 GB possono generare costi minimi per lo storage aggiuntivo.

## Rete

```
VCN 10.0.0.0/16 (oke-vcn)
├── API Endpoint Subnet  10.0.0.0/28   (public) - K8s API :6443
├── Node Subnet          10.0.1.0/24   (public) - Worker nodes
├── LB Subnet            10.0.2.0/24   (public) - HTTP/HTTPS
└── Micro VM Subnet      10.0.3.0/28   (public) - VM standalone
```

- Flannel CNI (pods: 10.244.0.0/16, services: 10.96.0.0/16)
- Tutte le subnet pubbliche (evita NAT Gateway a pagamento)
- Service Gateway per accesso OCIR gratuito

## Struttura Progetto

```
OCI/
├── terraform/
│   ├── provider.tf              # Provider OCI
│   ├── variables.tf             # Variabili input
│   ├── data.tf                  # Data sources (AD, immagini, K8s versions)
│   ├── network.tf               # VCN, subnet, gateways, security lists
│   ├── oke.tf                   # Cluster OKE + node pools
│   ├── micro.tf                 # Micro VM standalone
│   ├── iam.tf                   # IAM Dynamic Group + Policy (Instance Principal Grafana)
│   ├── objectstorage.tf         # Bucket Object Storage (Velero)
│   ├── ocir.tf                  # Container Registry (OCIR)
│   ├── outputs.tf               # Output values
│   ├── terraform.tfvars         # Configurazione (gitignored)
│   └── terraform.tfvars.example # Template
│
├── ansible/
│   ├── ansible.cfg              # Configurazione Ansible
│   ├── inventory/
│   │   ├── hosts.yml            # Inventory micro VM (gitignored, auto-generato)
│   │   └── hosts.yml.example    # Template inventory
│   ├── vars/
│   │   ├── oke.yml.example          # Template configurazione (non-sensibile)
│   │   └── oke-vault.yml.example    # Template secret (da criptare con ansible-vault)
│   └── playbooks/
│       ├── post-cluster-setup.yml        # Infrastruttura base (Traefik, cert-manager, metrics, dashboard)
│       ├── ci-setup.yml                  # CI/CD (ArgoCD + Tekton + Kaniko)
│       ├── security-setup.yml            # Security (Kyverno policy engine)
│       ├── backup-setup.yml              # Backup & DR (Velero + OCI Object Storage)
│       ├── observability-cluster-setup.yml  # Observability K8s (Prometheus, Loki, Promtail, OTEL)
│       ├── observability-vm-setup.yml       # Grafana su micro VM (Podman)
│       ├── domain-setup.yml                 # HTTPS routing via sottodomini (IngressRoute)
│       └── reverse-proxy-setup.yml          # TCP forwarding su micro-gw (firewalld DNAT → Traefik)
│
├── scripts/
│   ├── deploy.sh                # Provisioning infrastruttura (Terraform + kubeconfig + wait nodes)
│   ├── post-setup.sh            # Configurazione cluster (Ansible post-cluster-setup)
│   ├── destroy.sh               # Distruggi tutto
│   ├── get-kubeconfig.sh        # Configura kubectl
│   ├── generate-ssh-key.sh      # Genera chiavi SSH
│   ├── generate-inventory.sh    # Genera inventory Ansible da Terraform output
│   ├── generate-vars.sh         # Genera ansible/vars/oke.yml da Terraform output
│   ├── generate-summary.sh     # Genera docs/deploy-summary.md con tutti gli output
│   ├── list-instances.sh        # Lista istanze OCI
│   └── get_oci_info.sh          # Info configurazione OCI
│
├── docs/
│   └── deploy-summary.md       # Output deploy (gitignored, generato da generate-summary.sh)
│
├── README.md
└── .gitignore
```

## Prerequisiti

1. Account OCI con free tier
2. [Terraform](https://www.terraform.io/) >= 1.0
3. [OCI CLI](https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm) configurato
4. [kubectl](https://kubernetes.io/docs/tasks/tools/)
5. [Helm](https://helm.sh/) (per NGINX Ingress)
6. [Ansible](https://docs.ansible.com/) (per post-setup)
7. Chiavi API OCI configurate

## Quick Start

```bash
# 1. Genera chiavi SSH
./scripts/generate-ssh-key.sh

# 2. Configura terraform.tfvars
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
# Edita con i tuoi dati OCI

# 3. Provisioning infrastruttura (Terraform + kubeconfig + wait nodes)
./scripts/deploy.sh

# 4. Genera variabili Ansible da Terraform output (oppure copia manuale)
./scripts/generate-vars.sh
./scripts/generate-inventory.sh
# Oppure manualmente: cp ansible/vars/oke.yml.example ansible/vars/oke.yml

# 5. Configurazione cluster (Ansible — infrastruttura base)
./scripts/post-setup.sh

# 6. (Opzionale) CI/CD - ArgoCD + Tekton + Kaniko
ansible-playbook ansible/playbooks/ci-setup.yml

# 7. (Opzionale) Security - Kyverno policy engine
ansible-playbook ansible/playbooks/security-setup.yml

# 8. (Opzionale) Backup & DR - Velero + OCI Object Storage
ansible-playbook ansible/playbooks/backup-setup.yml

# 9. (Opzionale) Observability - Prometheus + Loki + Grafana
ansible-playbook ansible/playbooks/observability-cluster-setup.yml
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/observability-vm-setup.yml

# 10. (Opzionale) Domain Setup - HTTPS via sottodomini
# Configurare base_domain in ansible/vars/oke.yml, creare DNS A record,
# poi ri-eseguire post-cluster-setup.yml (Traefik con ACME) e domain-setup.yml
ansible-playbook ansible/playbooks/post-cluster-setup.yml
ansible-playbook ansible/playbooks/domain-setup.yml
# Per Grafana: ri-eseguire anche observability-vm-setup.yml
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/observability-vm-setup.yml

# 11. (Opzionale) TCP Forwarding - micro-gw (IP stabile → Traefik K8s)
# DNS → micro-gw (firewalld DNAT) → Traefik K8s (TLS ACME + L7 routing)
# Configurare install_reverse_proxy: true in ansible/vars/oke.yml
ansible-playbook ansible/playbooks/post-cluster-setup.yml       # Traefik con ACME
ansible-playbook ansible/playbooks/domain-setup.yml             # IngressRoute
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/reverse-proxy-setup.yml  # firewalld DNAT
```

## Deploy Manuale

### Terraform

```bash
cd terraform
terraform init
terraform plan
terraform apply    # ~15-20 minuti
```

### Kubeconfig

```bash
./scripts/get-kubeconfig.sh
# oppure manualmente:
oci ce cluster create-kubeconfig \
  --cluster-id $(cd terraform && terraform output -raw cluster_id) \
  --file $HOME/.kube/config \
  --region eu-milan-1 \
  --token-version 2.0.0 \
  --kube-endpoint PUBLIC_ENDPOINT
```

### Verifica

```bash
kubectl get nodes -o wide
kubectl get nodes --show-labels | grep workload
```

Output atteso:
```
NAME          STATUS   ROLES   AGE   VERSION   LABELS
oke-xxxxx     Ready    node    5m    v1.xx     workload=heavy
oke-yyyyy     Ready    node    5m    v1.xx     workload=light
```

### Micro VMs

```bash
# SSH alle micro VM (Oracle Linux, utente: opc)
cd terraform
terraform output ssh_micro_commands
```

## Ansible Playbooks

Playbook separati, eseguibili indipendentemente e in qualsiasi momento.

### 1. Infrastruttura base (`post-cluster-setup.yml`)

```bash
ansible-playbook ansible/playbooks/post-cluster-setup.yml
```

| App | Namespace | Nodo | Descrizione |
|---|---|---|---|
| **Traefik** | traefik | light | Ingress controller, NodePort 30080/30443, dashboard :30090 |
| **cert-manager** | cert-manager | light | Certificati TLS automatici Let's Encrypt |
| **metrics-server** | kube-system | light | Abilita `kubectl top` e HPA |
| **K8s Dashboard** | monitoring | light | Web UI gestione cluster |

### 2. CI/CD (`ci-setup.yml`)

```bash
ansible-playbook ansible/playbooks/ci-setup.yml
```

| App | Namespace | Nodo | Descrizione |
|---|---|---|---|
| **ArgoCD** | argocd | light | GitOps continuous delivery, UI via `/argocd` |
| **Tekton Pipelines** | tekton-pipelines | - | CI/CD engine cloud-native, Dashboard via `/tekton` |
| **Kaniko** | tekton-pipelines | - | Build immagini Docker senza Docker daemon |

Risorse Tekton create automaticamente:
- **Task `kaniko-build`** - build + push immagine su OCIR
- **Task `git-clone`** - clone repository (dal catalogo Tekton)
- **Pipeline `build-and-push`** - pipeline completa clone + build
- **ServiceAccount `tekton-build`** - con credenziali OCIR

### 3. Security (`security-setup.yml`)

```bash
ansible-playbook ansible/playbooks/security-setup.yml
```

| App | Namespace | Nodo | Descrizione |
|---|---|---|---|
| **Kyverno** | kyverno | light | Policy engine per validazione/mutazione risorse K8s |

Policy incluse:

| Policy | Severity | Descrizione |
|---|---|---|
| `disallow-privileged-containers` | high | Blocca container privilegiati |
| `disallow-host-namespaces` | high | Blocca hostNetwork, hostPID, hostIPC |
| `disallow-latest-tag` | medium | Richiede tag esplicito (no `:latest`) |
| `require-resource-limits` | medium | Obbliga `resources.limits` (cpu + memory) |
| `require-labels` | low | Obbliga label `app.kubernetes.io/name` |
| `restrict-image-registries` | high | Solo immagini OCIR nel namespace `events` |

Modalita' di enforcement configurabile in `oke.yml`:
- `Audit` (default) - solo log, non blocca i deploy
- `Enforce` - blocca le risorse non conformi

### 4. Backup & DR (`backup-setup.yml`)

```bash
ansible-playbook ansible/playbooks/backup-setup.yml
```

| App | Namespace | Nodo | Descrizione |
|---|---|---|---|
| **Velero** | velero | light | Backup e restore K8s su OCI Object Storage |

Terraform crea automaticamente:
- Bucket Object Storage `velero-backups` (free tier: 20 GB Standard)
- Customer Secret Key per accesso S3-compatible
- Repository OCIR privati per le immagini Docker
- Auth Token per docker login

Dopo `terraform apply`, recupera le credenziali per `ansible/vars/oke.yml`:
```bash
cd terraform
terraform output velero_s3_endpoint          # velero_s3_url
terraform output velero_s3_access_key        # velero_aws_access_key_id
terraform output -raw velero_s3_secret_key   # velero_aws_secret_access_key
```

Schedule automatici:
- `daily-full-backup` - ogni notte alle 02:00 (ns: events, monitoring) - retention 7 giorni
- `weekly-cluster-backup` - domenica alle 03:00 (tutto il cluster) - retention 30 giorni

### OCIR (Container Registry)

Terraform crea i repository OCIR privati e l'auth token per docker login.

```bash
# Recupera credenziali OCIR dagli output Terraform
cd terraform
terraform output ocir_endpoint              # eu-milan-1.ocir.io
terraform output ocir_docker_server         # eu-milan-1.ocir.io/<namespace>
terraform output objectstorage_namespace    # namespace tenancy
terraform output -raw ocir_auth_token       # auth token (sensibile)
terraform output ocir_repositories          # full path dei repo

# Docker login
docker login eu-milan-1.ocir.io \
  -u "<namespace>/<email>" \
  -p "$(terraform output -raw ocir_auth_token)"

# Push immagine
docker tag myapp:latest eu-milan-1.ocir.io/<namespace>/events/backoffice:latest
docker push eu-milan-1.ocir.io/<namespace>/events/backoffice:latest
```

Repository creati: `events/backoffice`, `events/scraping` (configurabili in `terraform.tfvars`).

### 5. Observability (`observability-cluster-setup.yml` + `observability-vm-setup.yml`)

Architettura ibrida: backend nel cluster K8s, Grafana su micro VM standalone.

```
Micro VM (micro-monitor, 1 GB)       K8s Cluster (light node, 6 GB)
┌─────────────────────────┐          ┌────────────────────────────────┐
│ Grafana (Podman) :3000  │──query──→│ Prometheus   :31090 (NodePort) │
│ ~300 MB                 │──query──→│ Loki         :31100 (NodePort) │
│ 8 dashboard provisioned │──query──→│ Tempo        (trace backend)   │
│ alert rules (K8s labels)│          │ Alertmanager :31093 (NodePort) │
│ datasources auto-config │          │ OTEL Collect (DaemonSet, contrib)│
└─────────────────────────┘          │   → spanmetrics → Prometheus   │
                                     │   → traces     → Tempo         │
                                     │ Promtail     (DaemonSet)       │
                                     │   → pipeline stages JSON parse │
                                     │ kube-state-metrics             │
                                     │ node-exporter (DaemonSet)      │
                                     │ Redis Exporter  (condizionale) │
                                     │ Celery Exporter (condizionale) │
                                     └────────────────────────────────┘
```

```bash
# Step 1: Installa stack K8s (Prometheus, Loki, Promtail, OTEL Collector)
ansible-playbook ansible/playbooks/observability-cluster-setup.yml

# Step 2: Genera inventory micro VM da Terraform output
./scripts/generate-inventory.sh

# Step 3: Installa Grafana su micro-monitor VM
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/observability-vm-setup.yml
```

| Componente | Tipo | Nodo | Porta | Resource limits |
|---|---|---|---|---|
| **Prometheus** (server + kube-state-metrics + node-exporter) | Deployment + DaemonSet | light | NodePort 31090 | 500m/512Mi |
| **Alertmanager** (gestione alert) | Deployment | light | NodePort 31093 | 100m/128Mi |
| **Loki** (single binary) | StatefulSet | light | NodePort 31100 | 250m/256Mi |
| **Promtail** (pipeline stages: CRI + JSON parse) | DaemonSet | tutti | - | 100m/64Mi |
| **OTEL Collector** (contrib, spanmetrics + Tempo export) | DaemonSet | tutti | gRPC 4317, HTTP 4318, metrics 8889 | 200m/128Mi |
| **Tempo** (distributed tracing, local storage) | Deployment | light | ClusterIP | 250m/256Mi |
| **Redis Exporter** (condizionale) | Deployment | light | ClusterIP 9121 | 50m/64Mi |
| **Celery Exporter** (condizionale) | Deployment | light | ClusterIP 9808 | 50m/64Mi |
| **Grafana** (Podman, 8 dashboard + alert rules) | micro VM | micro-monitor | 3000 | ~300 MB |

**OCI Native Datasources** (plugin Grafana):
- **OCI Monitoring** (`oci-metrics-datasource`) - metriche infra: CPU, RAM, disco, rete di VM, nodi OKE, VCN
- **OCI Logging** (`oci-logs-datasource`) - log centralizzati OCI

Auth via **Instance Principal**: Terraform crea un Dynamic Group + IAM Policy che permette alla micro-monitor VM di leggere metriche e log OCI senza chiavi API. Il container Grafana si autentica automaticamente tramite il metadata service dell'istanza.

Risorse stimate sul nodo light: ~1.4 GB / 6 GB = ~23% (con Tempo). Redis/Celery Exporter aggiungono ~128 Mi quando abilitati.

Verifica:
```bash
kubectl get pods -n monitoring                                      # tutti Running
kubectl get svc -n monitoring                                       # NodePort visibili
curl http://<k8s-node-ip>:31090/api/v1/status/config               # Prometheus
curl http://<k8s-node-ip>:31100/ready                               # Loki
http://<micro-monitor-ip>:3000                                      # Grafana UI
sudo systemctl status grafana                                       # su micro VM
```

### Configurazione

Ogni applicazione e' attivabile/disattivabile in `ansible/vars/oke.yml`:
```yaml
# Infrastruttura base (post-cluster-setup.yml)
install_traefik: true          # Ingress controller
install_cert_manager: true     # TLS con Let's Encrypt
install_metrics_server: true   # kubectl top + HPA
install_dashboard: true        # Web UI

# CI/CD (ci-setup.yml)
install_argocd: true           # GitOps CD
install_tekton: true           # Tekton + Kaniko

# Security (security-setup.yml)
install_kyverno: true          # Policy engine
kyverno_enforcement_mode: "Audit"  # Audit o Enforce

# Backup (backup-setup.yml)
install_velero: true           # Backup & DR

# Observability (observability-cluster-setup.yml + observability-vm-setup.yml)
install_prometheus: true       # Prometheus + kube-state-metrics + node-exporter + extraScrapeConfigs
install_alertmanager: true     # Alertmanager (gestione alert)
install_loki: true             # Loki (SingleBinary)
install_promtail: true         # Promtail (DaemonSet, pipeline stages JSON parse)
install_otel_collector: true   # OTEL Collector (contrib, spanmetrics → Prometheus, traces → Tempo)
install_tempo: true            # Grafana Tempo (distributed tracing, sostituisce Jaeger)
install_redis_exporter: false  # Redis Exporter (abilita dopo deploy app su K8s)
install_celery_exporter: false # Celery Exporter (abilita dopo deploy app su K8s)
install_grafana_vm: true       # Grafana su micro VM (Podman)
install_grafana_dashboards: true   # 8 dashboard JSON provisioned
install_grafana_alerting: true     # Alert rules K8s-adapted

# Domain Setup (domain-setup.yml) — scegliere una opzione:
install_oauth2_proxy: false        # Google SSO (OAuth2 Proxy)

# Reverse Proxy (reverse-proxy-setup.yml)
install_reverse_proxy: false       # TCP forwarding su micro-gw (IP stabile → Traefik)
# Auth per-servizio (true = auth middleware, false = no auth):
auth_traefik: true                 # Traefik Dashboard
auth_prometheus: true              # Prometheus
auth_alertmanager: true            # Alertmanager
auth_loki: true                    # Loki
auth_dashboard: true               # K8s Dashboard
auth_tempo: true                   # Tempo
```

### Traefik

Ingress controller con dashboard web integrata:

```bash
# Dashboard Traefik: http://<NODE_IP>:30090/dashboard/
# (nota: lo slash finale e' obbligatorio)

# Verifica
kubectl get pods -n traefik
kubectl get svc -n traefik
kubectl get ingressroute -A       # CRD Traefik
```

Esempio IngressRoute (CRD nativo Traefik):
```yaml
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: myapp
  namespace: apps
spec:
  entryPoints:
    - websecure
  routes:
    - match: Host(`app.example.com`)
      kind: Rule
      services:
        - name: myapp
          port: 80
  tls:
    certResolver: default
```

### ArgoCD

GitOps continuous delivery - sincronizza lo stato del cluster con un repository Git.

```bash
# Password admin iniziale
kubectl -n clusters get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d; echo

# Accesso via port-forward (http://localhost:8080)
kubectl -n clusters port-forward svc/argocd-server 8080:80

# Oppure via Traefik: http://<NODE_IP>:30080/argocd/

# CLI (opzionale)
argocd login localhost:8080 --username admin --insecure
```

### Tekton + Kaniko

CI/CD cloud-native: Tekton orchestra le pipeline, Kaniko builda immagini Docker senza Docker daemon.

Il setup include:
- **Tekton Pipelines** - engine CI/CD
- **Tekton Dashboard** - UI web accessibile via `/tekton` su Traefik
- **Task `kaniko-build`** - builda e pusha immagini su OCIR
- **Task `git-clone`** - clona repository dal catalogo Tekton
- **Pipeline `build-and-push`** - pipeline completa git-clone + kaniko-build
- **ServiceAccount `tekton-build`** - con credenziali OCIR

```bash
# Dashboard Tekton: http://<NODE_IP>:30080/tekton/
# Oppure port-forward: kubectl -n tekton-pipelines port-forward svc/tekton-dashboard 9097

# Verifica risorse
kubectl get tasks,pipelines -n tekton-pipelines
kubectl get pipelineruns -n tekton-pipelines
```

Esempio PipelineRun per buildare un'immagine:
```yaml
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata:
  generateName: build-myapp-
  namespace: tekton-pipelines
spec:
  pipelineRef:
    name: build-and-push
  params:
    - name: repo-url
      value: "https://github.com/user/myapp.git"
    - name: revision
      value: "main"
    - name: image
      value: "eu-milan-1.ocir.io/NAMESPACE/myapp:latest"
  workspaces:
    - name: shared-workspace
      volumeClaimTemplate:
        spec:
          accessModes: [ReadWriteOnce]
          resources:
            requests:
              storage: 1Gi
  taskRunTemplate:
    serviceAccountName: tekton-build
```

```bash
# Lancia la pipeline
kubectl create -f pipelinerun.yaml

# Segui i log
tkn pipelinerun logs -f -n tekton-pipelines
```

### K8s Dashboard

```bash
# Genera token di accesso
kubectl -n monitoring create token dashboard-admin

# Port-forward (accesso locale su https://localhost:8443)
kubectl -n monitoring port-forward svc/kubernetes-dashboard-kong-proxy 8443:443
```

### cert-manager

Vengono creati 2 ClusterIssuer (solver HTTP-01 via Traefik):
- `letsencrypt-staging` - test (no rate limit)
- `letsencrypt-prod` - produzione

Esempio Ingress con TLS automatico:
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
    - hosts: [app.example.com]
      secretName: app-tls
```

## Security Lists

| Subnet | Porta | Sorgente | Descrizione |
|---|---|---|---|
| API | 6443 | 0.0.0.0/0 | Kubernetes API |
| API | 12250 | 10.0.1.0/24 | OKE control plane |
| Node | 22 | 0.0.0.0/0 | SSH |
| Node | all | 10.0.0.0/16 | Intra-VCN |
| Node | 10250 | 10.0.0.0/28 | Kubelet API |
| Node | 30000-32767 | 0.0.0.0/0 | NodePort |
| Node | 80 | 0.0.0.0/0 | HTTP (Traefik hostPort / ACME) |
| Node | 443 | 0.0.0.0/0 | HTTPS (Traefik hostPort / TLS) |
| LB | 80, 443 | 0.0.0.0/0 | HTTP/HTTPS |
| Micro | 22, 80, 443 | 0.0.0.0/0 | SSH, HTTP/S |
| Micro | 3000 | 0.0.0.0/0 | Grafana |
| Micro | 3001 | 0.0.0.0/0 | Uptime Kuma |
| Micro | 9090-9100 | 10.0.0.0/16 | Prometheus (VCN) |

## Domain Setup (HTTPS via sottodomini)

Configurazione opzionale per accedere ai servizi tramite sottodomini HTTPS con certificati Let's Encrypt automatici.

### Architettura

```
Internet → DNS
  │
  ├── *.example.com → K8s Node (light) Public IP
  │     └── Traefik (hostPort 80/443, ACME Let's Encrypt)
  │           ├── traefik.example.com    → Traefik Dashboard (auth)
  │           ├── argocd.example.com     → ArgoCD server
  │           ├── tekton.example.com     → Tekton Dashboard
  │           ├── prometheus.example.com → Prometheus (auth)
  │           ├── alertmanager.example.com → Alertmanager (auth)
  │           ├── loki.example.com       → Loki (auth)
  │           ├── dashboard.example.com  → K8s Dashboard (auth)

  │           └── auth.example.com       → OAuth2 Proxy (Google SSO callback)
  │
  └── grafana.example.com → Traefik → ExternalName → micro-monitor:3000

Auth = OAuth2 Proxy (Google SSO)
```

### Servizi e URL

| Servizio | URL | Auth | Target |
|---|---|---|---|
| Traefik Dashboard | `https://traefik.DOMAIN` | OAuth2 Proxy | `api@internal` |
| ArgoCD | `https://argocd.DOMAIN` | Nativa (admin) | `argocd-server:80` |
| Tekton Dashboard | `https://tekton.DOMAIN` | - | `tekton-dashboard:9097` |
| Prometheus | `https://prometheus.DOMAIN` | OAuth2 Proxy | `prometheus-server:80` |
| Alertmanager | `https://alertmanager.DOMAIN` | OAuth2 Proxy | `prometheus-alertmanager:9093` |
| Loki | `https://loki.DOMAIN` | OAuth2 Proxy | `loki:3100` |
| K8s Dashboard | `https://dashboard.DOMAIN` | OAuth2 Proxy | `kubernetes-dashboard-kong-proxy:443` |
| Tempo | — | Datasource Grafana | `tempo:3100` (interno) |
| OAuth2 Proxy | `https://auth.DOMAIN` | - (callback Google) | `oauth2-proxy:4180` |
| Grafana | `https://grafana.DOMAIN` | Nativa (admin) | ExternalName → `micro-monitor:3000` |

### Requisiti DNS

Creare **A record** per ogni sottodominio:

| Sottodominio | IP |
|---|---|
| `traefik`, `argocd`, `tekton`, `prometheus`, `alertmanager`, `loki`, `dashboard`, `grafana`, `auth` | IP pubblico nodo K8s **light** (o micro-gw se reverse proxy attivo) |

### Setup

```bash
# 1. Configurare in ansible/vars/oke.yml
base_domain: "example.com"

# Scegliere UNA delle due opzioni di autenticazione:

# Google SSO (OAuth2 Proxy):
install_oauth2_proxy: true
oauth2_proxy_client_id: "xxx.apps.googleusercontent.com"
oauth2_proxy_client_secret: "GOCSPX-xxx"
oauth2_proxy_cookie_secret: "xxx"  # python3 -c 'import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())'
oauth2_proxy_allowed_emails:
  - "your.email@gmail.com"
# Google Cloud Console: Credentials → OAuth 2.0 Client ID (tipo: Web application)
# Authorized redirect URI: https://auth.example.com/oauth2/callback

# 2. Aprire porte 80/443 su node subnet (se non gia' fatto)
cd terraform && terraform apply

# 3. Ri-eseguire post-cluster-setup (Traefik con ACME + hostPort)
ansible-playbook ansible/playbooks/post-cluster-setup.yml

# 4. Creare DNS A record → IP corrette (includere auth.DOMAIN se OAuth2 Proxy)

# 5. Creare IngressRoute HTTPS per tutti i servizi
ansible-playbook ansible/playbooks/domain-setup.yml

# 6. (Opzionale) Grafana su micro VM
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/observability-vm-setup.yml
```

### Verifica

```bash
kubectl get ingressroute -A
curl -I https://argocd.example.com         # 200
curl -I https://grafana.example.com        # 200 (via Traefik → ExternalName)

# OAuth2 Proxy (Google SSO):
curl -I https://traefik.example.com        # 302 → Google sign-in
curl -I https://grafana.example.com        # 200 (auth nativa Grafana)
kubectl get pods -n traefik | grep oauth2  # oauth2-proxy Running

# Certificati TLS
echo | openssl s_client -servername prometheus.example.com \
  -connect <K8S_NODE_IP>:443 2>/dev/null | openssl x509 -noout -issuer
# issuer: Let's Encrypt
```

> **Nota**: I NodePort (30080/30443) restano attivi per comunicazione interna VCN (es. Grafana → Prometheus/Loki). Le IngressRoute PathPrefix esistenti in `ci-setup.yml` restano come fallback per chi non configura `base_domain`.

### TCP Forwarding (micro-gw — IP stabile)

L'IP pubblico del nodo K8s light e' **effimero** — cambia se il nodo viene ricreato (scaling, upgrade, crash), rompendo tutti i DNS A record. La micro VM `micro-gw` ha invece un IP pubblico stabile.

**Soluzione**: usare micro-gw come TCP forwarder via firewalld DNAT. DNS punta a micro-gw → firewalld inoltra traffico TCP grezzo a Traefik nel cluster → Traefik gestisce TLS (Let's Encrypt ACME) e L7 routing.

```
Internet → DNS → micro-gw:80/443 (firewalld DNAT, IP stabile)
                   │
                   ├── :443 → k8s light node:30443 → Traefik (TLS ACME + L7 routing)
                   └── :80  → k8s light node:30080 → Traefik (HTTP→HTTPS redirect)
```

Traefik riceve il traffico TCP grezzo, termina TLS con Let's Encrypt ACME, e fa L7 routing basato sull'header `Host:` verso le IngressRoute.

#### Differenze rispetto al modo diretto

| | Traefik diretto | TCP Forwarding (micro-gw) |
|---|---|---|
| **TLS** | Traefik (ACME, hostPort 80/443) | Traefik (ACME, via DNAT da micro-gw) |
| **DNS target** | IP nodo K8s light (effimero) | IP micro-gw (stabile) |
| **micro-gw** | Non usata | firewalld DNAT (trasparente) |

#### Auth per-servizio

Ogni servizio protetto puo' essere escluso dall'auth middleware:

```yaml
# In ansible/vars/oke.yml — default: true (auth abilitata)
auth_traefik: true       # Traefik Dashboard con auth
auth_prometheus: true    # Prometheus con auth
auth_alertmanager: true  # Alertmanager con auth
auth_loki: true          # Loki con auth
auth_dashboard: true     # K8s Dashboard con auth
auth_grafana: false      # Grafana SENZA auth OAuth2 (esempio)
```

Servizi con auth nativa (ArgoCD, Grafana) non usano mai il middleware.

#### Setup

```bash
# 1. Configurare in ansible/vars/oke.yml
install_reverse_proxy: true
micro_monitor_private_ip: "10.0.3.8"  # terraform output micro_vm_private_ips
auth_prometheus: true     # scegli per ogni servizio
auth_grafana: false       # esempio: grafana senza auth OAuth2

# 2. Ri-eseguire post-cluster-setup (Traefik senza hostPort/ACME)
ansible-playbook ansible/playbooks/post-cluster-setup.yml

# 3. Creare IngressRoute (con entryPoint web + auth per-servizio)
ansible-playbook ansible/playbooks/domain-setup.yml

# 4. Configurare TCP forwarding su micro-gw (firewalld DNAT)
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/reverse-proxy-setup.yml

# 5. Aggiornare DNS: TUTTI i sottodomini → IP micro-gw
```

#### Verifica

```bash
# Firewalld status su micro-gw
ssh micro-gw sudo firewall-cmd --list-forward-ports
ssh micro-gw sudo firewall-cmd --query-masquerade
ssh micro-gw sysctl net.ipv4.ip_forward

# Test HTTPS
curl -I https://prometheus.example.com   # 302 (OAuth2 → Google sign-in)
curl -I https://argocd.example.com       # 200 (auth nativa)
curl -I https://grafana.example.com      # 200 (se auth_grafana: false)
```

## Comandi Utili

```bash
# Cluster
kubectl get nodes
kubectl get pods -A
kubectl get ns
kubectl top nodes                    # richiede metrics-server
kubectl top pods -A                  # metriche per pod

# Traefik
kubectl get pods -n traefik
kubectl get svc -n traefik
kubectl get ingressroute -A          # IngressRoute CRD
# Dashboard: http://<NODE_IP>:30090/dashboard/ (senza domain)
# Dashboard: https://traefik.<DOMAIN> (con domain setup)

# ArgoCD
kubectl -n clusters get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo
kubectl -n clusters port-forward svc/argocd-server 8080:80
# Oppure: https://argocd.<DOMAIN> (con domain setup)

# Tekton + Kaniko
kubectl get tasks,pipelines -n tekton-pipelines
kubectl get pipelineruns -n tekton-pipelines
# Dashboard: https://tekton.<DOMAIN> (con domain setup)

# Kyverno (security)
kubectl get clusterpolicy                           # lista policy
kubectl get policyreport -A                         # report violazioni
kubectl describe clusterpolicy <nome-policy>        # dettaglio policy

# Velero (backup)
velero backup get                    # lista backup
velero schedule get                  # lista schedule
velero backup create manual --include-namespaces events   # backup manuale
velero restore create --from-backup manual                # restore

# cert-manager
kubectl get clusterissuer            # stato issuer Let's Encrypt
kubectl get certificates -A          # certificati emessi

# Dashboard K8s
kubectl -n monitoring create token dashboard-admin
kubectl -n monitoring port-forward svc/kubernetes-dashboard-kong-proxy 8443:443

# Observability
kubectl get pods -n monitoring                         # stato pod
kubectl get svc -n monitoring                          # servizi e NodePort
curl http://<K8S_NODE_IP>:31090/api/v1/status/config   # Prometheus health
curl http://<K8S_NODE_IP>:31100/ready                   # Loki health
# Grafana: http://<MICRO_MONITOR_IP>:3000 (senza domain)
# Grafana: https://grafana.<DOMAIN> (con domain setup, via Traefik → ExternalName)
ssh opc@<MICRO_MONITOR_IP> sudo systemctl status grafana  # stato Grafana
# In Grafana: OCI Monitoring datasource → query metriche infra OCI
# Metriche OCI: CpuUtilization, MemoryUtilization, NetworkBytesIn/Out, DiskBytesRead/Written

# TCP Forwarding (micro-gw)
ssh micro-gw sudo firewall-cmd --list-forward-ports       # regole DNAT
ssh micro-gw sudo firewall-cmd --query-masquerade          # masquerade attivo
ssh micro-gw sysctl net.ipv4.ip_forward                    # IP forwarding

# Terraform
terraform output                    # Tutti gli output
terraform output cluster_endpoint   # Endpoint K8s API
terraform output ssh_micro_commands # SSH micro VMs

# Distruzione
./scripts/destroy.sh
```

## Troubleshooting

### I nodi non diventano Ready
```bash
# Verifica stato node pool
oci ce node-pool get --node-pool-id $(cd terraform && terraform output -raw heavy_pool_id) \
  --query 'data.nodes[].{"name":"name","state":"lifecycle-state"}' --output table
```

### kubectl non si connette
```bash
# Rigenera kubeconfig
./scripts/get-kubeconfig.sh
# Verifica
kubectl cluster-info
```

### Quote OCI esaurite
```bash
oci limits resource-availability get \
  --compartment-id <compartment-ocid> \
  --service-name compute \
  --limit-name standard-a1-core-count \
  --availability-domain <ad-name>
```

## Sicurezza

- `terraform.tfvars`, `ansible/vars/oke.yml` e `oke-vault.yml` sono in `.gitignore`
- Mai committare chiavi private, token, o kubeconfig
- Limitare SSH a IP specifici modificando le security list in `network.tf`
- Usare OCIR con repository privati
- Ruotare auth token periodicamente

### Ansible Vault (cifratura secret)

I secret sono separati dalla configurazione:
- `ansible/vars/oke.yml` — configurazione non-sensibile (porte, flag, risorse)
- `ansible/vars/oke-vault.yml` — secret criptati (password, token, chiavi API)

```bash
# Setup iniziale (generate-vars.sh offre cifratura automatica)
./scripts/generate-vars.sh

# Cifratura manuale
ansible-vault encrypt ansible/vars/oke-vault.yml

# Editare secret criptati
ansible-vault edit ansible/vars/oke-vault.yml

# Eseguire playbook con vault
ansible-playbook ansible/playbooks/post-cluster-setup.yml --ask-vault-pass

# Per evitare --ask-vault-pass ogni volta:
echo 'LA_TUA_PASSWORD' > ~/.vault_pass && chmod 600 ~/.vault_pass
# Decommentare vault_password_file in ansible/ansible.cfg
```

Secret gestiti in `oke-vault.yml`:
- `ocir_auth_token` — token OCIR per imagePullSecret
- `grafana_admin_password` — password admin Grafana
- `velero_aws_access_key_id` / `velero_aws_secret_access_key` — credenziali S3 backup
- `redis_k8s_password` / `celery_broker_url` — credenziali Redis/Celery
- `oauth2_proxy_client_id` / `client_secret` / `cookie_secret` — credenziali Google SSO

## License

MIT
