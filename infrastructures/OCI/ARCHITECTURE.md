# Analisi Architettura Cloud — Today Events

## 1. Panoramica

Piattaforma di aggregazione eventi che raccoglie dati da 50+ fonti italiane (Zero.eu, Today.it, Artribune), li valida attraverso una staging pipeline, e li espone via REST API a frontend React e consumer esterni.

**Stack**: Django 5.0 + DRF, PostgreSQL 16 + PostGIS, Redis 7, Celery, Scrapy 2.11, React 19 + TypeScript + Vite, Kubernetes (OKE su Oracle Cloud)

**Costo totale: 0 EUR** (Oracle Cloud Free Tier)

---

## 2. Topologia Infrastruttura (OCI Free Tier)

```
                          INTERNET
                             |
                        DNS A Record
                             |
                      +------v------+
                      |  micro-gw   |  1/8 OCPU, 1GB RAM
                      |  10.0.3.x   |  IP Pubblico Stabile
                      |-------------|
                      | firewalld   |  DNAT :80->30080, :443->30443
                      | WireGuard   |  VPN :51820 (10.10.0.0/24)
                      +------+------+
                             | TCP forwarding
              +--------------v------------------------------+
              |        OKE CLUSTER (BASIC - free)            |
              |        VCN: 10.0.0.0/16                      |
              |                                              |
              |  +-----------------+  +------------------+   |
              |  |  LIGHT NODE     |  |  HEAVY NODE      |   |
              |  |  1 OCPU / 6GB   |  |  3 OCPU / 18GB   |   |
              |  |  ARM64 (A1)     |  |  ARM64 (A1)      |   |
              |  |-----------------|  |------------------|   |
              |  | Traefik         |  | PostgreSQL+PostGIS|  |
              |  | cert-manager    |  | Redis            |   |
              |  | OAuth2 Proxy    |  | MinIO            |   |
              |  | metrics-server  |  | Celery worker/beat|  |
              |  | K8s Dashboard   |  | Backoffice Django|   |
              |  | Alertmanager    |  | Kong API Gateway |   |
              |  | WireGuard       |  | Prometheus       |   |
              |  | Velero + UI     |  | Grafana          |   |
              |  | Linkerd CP      |  | OTEL Collector   |   |
              |  | Linkerd Viz     |  | SonarQube        |   |
              |  | Konga           |  | Airflow          |   |
              |  | Backstage       |  +------------------+   |
              |  | Loki            |                          |
              |  | Tempo           |                          |
              |  | redis-exporter  |                          |
              |  | celery-exporter |                          |
              |  +-----------------+                          |
              +----------------------------------------------+
                             |
              +--------------v------------+
              |    micro-monitor          |  1/8 OCPU, 1GB RAM
              |    10.0.3.x              |
              |--------------------------|
              | Grafana (Podman)         |  Instance Principal (IAM)
              | Uptime Kuma              |  Datasource: Prometheus, Loki, Tempo
              +--------------------------+
```

### Risorse OCI Free Tier

| Risorsa | Spec | Limite Free Tier |
|---------|------|------------------|
| OKE Cluster | BASIC_CLUSTER | Gratuito |
| A1.Flex (Heavy) | 3 OCPU, 18GB RAM, 120GB boot | 4 OCPU / 24GB totali |
| A1.Flex (Light) | 1 OCPU, 6GB RAM, 40GB boot | (incluso sopra) |
| E2.1.Micro x2 | 1/8 OCPU, 1GB RAM, 50GB boot | 2 VM gratuite |
| Object Storage | velero-backups | 20GB Standard |
| OCIR | 2 repo privati | Gratuito |

### Rete VCN

| Subnet | CIDR | Uso |
|--------|------|-----|
| API Endpoint | 10.0.0.0/28 | K8s API :6443 |
| Node | 10.0.1.0/24 | Worker nodes |
| Load Balancer | 10.0.2.0/24 | Riservato (non usato) |
| Micro VM | 10.0.3.0/28 | micro-gw + micro-monitor |

| Rete K8s | CIDR |
|----------|------|
| Pods (Flannel CNI) | 10.244.0.0/16 |
| Services | 10.96.0.0/16 |
| VPN (WireGuard) | 10.10.0.0/24 |

---

## 3. Mappa Namespace Kubernetes

```
+-------------------------------------------------------------------+
|                     KUBERNETES NAMESPACES                           |
|                                                                    |
|  database            apps             airflow          devs        |
|  +--------------+   +------------+   +------------+  +----------+ |
|  | PostgreSQL   |   | Backoffice |   | Webserver  |  | Backstage| |
|  | Redis        |   | Kong       |   | Scheduler  |  | SonarQube| |
|  | MinIO        |   | Konga      |   +------------+  +----------+ |
|  | Celery W/B   |   +------------+                                 |
|  | redis-export |   scraping                                       |
|  | celery-export|   +------------+                                 |
|  +--------------+   | (pod       |  Pod effimeri Scrapy            |
|                     |  effimeri) |  via KubernetesPodOperator      |
|                     +------------+  RBAC: airflow-scheduler SA     |
|                                                                    |
|  monitoring          clusters         traefik         infra        |
|  +--------------+   +------------+   +------------+  +----------+ |
|  | Prometheus   |   | K8s Dashb. |   | Traefik    |  | cert-mgr | |
|  | Grafana      |   | ArgoCD     |   | OAuth2 Prx |  | linkerd  | |
|  | Loki         |   | Velero+UI  |   +------------+  | lnk-viz  | |
|  | Tempo        |   | Kyverno    |                    | wireguard| |
|  | OTEL Collect.|   +------------+                    +----------+ |
|  | Promtail     |                                                  |
|  | Alertmanager |                                                  |
|  +--------------+                                                  |
+-------------------------------------------------------------------+
```

---

## 4. Flusso Dati: Scraping -> API -> Storage

```
    FONTI DATI                     PIPELINE                        STORAGE
  +--------------+
  | Zero.eu      |--+
  | Today.it x50 |--+  Scrapy Spiders (6)
  | Artribune    |--+    |
  | LaLiguria    |--+    v
  | InLombardia  |--+  ValidationPipeline --> DropItem (invalid)
  +--------------+       |
                    HashGeneratorPipeline
                         | UUID + content_hash (SHA256)
                    ApiPipeline (batch 50 items)
                         | OAuth2 Client Credentials
                         v
              POST /api/external/v1/staging/bulk/
                         |
                    +----v----+
                    | Django  |
                    | DRF     |
                    +----+----+
                         |
              +----------+----------+
              v                     v
        ?sync=true             async (default)
              |                     |
         Processo               Celery Task
         sincrono           process_bulk_events
              |                     |
              v                     v
         201/200/400          202 + task_id
                                    |
                               Celery Worker
                                    |
                            Validate + Bulk Create
                                    |
                                    v
                         +------------------+
                         | PostgreSQL       |
                         | staging_events   |
                         | (UPSERT by uuid) |
                         +--------+---------+
                                  | ETL
                                  v
                         +------------------+
                         | production_events|
                         | (validated,final)|
                         +------------------+
                                  |
                                  v
                         Frontend React / API consumers
```

### Struttura Evento (Scrapy -> API)

```json
{
  "uuid": "sha256[:16]",
  "content_hash": "sha256[:16]",
  "source": "city_today",
  "title": "Concerto Jazz",
  "category": ["musica", "jazz"],
  "section": {"teatro": {"rassegna": "...", "cast": "..."}},
  "city": {
    "city_name": "Milano",
    "location_name": "Blue Note",
    "location_address": "Via Borsieri 37",
    "location_coordinates": {"lat": 45.48, "lng": 9.18}
  },
  "dates": {
    "date_start": "2026-02-15",
    "time_start": "21:00:00",
    "date_end": "2026-02-15"
  },
  "url": "https://...",
  "description": "...",
  "image_url": "https://...",
  "price": "25,00 EUR",
  "scraped_at": "2026-02-05T14:30:00Z"
}
```

### Pipeline Scrapy (ordine esecuzione)

| # | Pipeline | Azione |
|---|----------|--------|
| 100 | ValidationPipeline | Verifica campi obbligatori, pulisce testo, normalizza date |
| 200 | HashGeneratorPipeline | Genera UUID (title+date+location) e content_hash |
| 300 | ApiPipeline | Batch 50 items, POST bulk endpoint con OAuth2 |

---

## 5. Flusso Network: Request HTTP

```
Client Browser
    |
    | HTTPS (*.oci.santocaruso.eu)
    v
micro-gw (firewalld DNAT)
    | TCP :443 -> :30443
    v
Traefik (NodePort 30443, namespace: traefik)
    | TLS termination (Let's Encrypt via cert-manager)
    | Host-based routing
    |
    +-- api.oci.santocaruso.eu -------> Kong (apps:8000)
    |                                     | rate-limiting, oauth2/oidc
    |                                     | prometheus, cors, http-log
    |                                     v
    |                                 Backoffice Django (apps:8000)
    |
    +-- events.oci.santocaruso.eu ----> Backoffice (apps:8000) [Web UI]
    +-- grafana.oci.santocaruso.eu ---> Grafana (monitoring:3000)
    +-- konga.oci.santocaruso.eu -----> Konga (apps:1337) [+ google-auth]
    +-- backstage.oci.santocaruso.eu -> Backstage (devs:7007) [+ google-auth]
    +-- sonarqube.oci.santocaruso.eu -> SonarQube (devs:9000)
    +-- minio.oci.santocaruso.eu -----> MinIO Console (database:9001) [+ google-auth]
    +-- s3.oci.santocaruso.eu --------> MinIO API (database:9000)
    +-- argocd.oci.santocaruso.eu ----> ArgoCD (clusters:443)
    +-- linkerd.oci.santocaruso.eu ---> Linkerd Viz (linkerd-viz) [+ google-auth]
    +-- traefik.oci.santocaruso.eu ---> Traefik Dashboard [+ google-auth]
    +-- velero.oci.santocaruso.eu ----> Velero UI (clusters:3000) [+ google-auth]
```

---

## 6. Flusso Celery: Task Asincroni

```
Django View (bulk endpoint)
    | .apply_async()
    v
Redis DB 1 (Broker) --- database:6379
    |
    v
Celery Worker (database namespace)
    | celery-config (ConfigMap)
    | celery-secret (Secret)
    |
    +-- process_bulk_events
    |     validate -> bulk_create -> result
    |     retry x3 (10s delay) on OperationalError
    |     fallback: save singolo se bulk_create fallisce
    |
    v
Django DB (TaskResult) <-- Result Backend
    |
    v
GET /api/external/v1/staging/bulk-status/{task_id}/
    -> PENDING / STARTED / SUCCESS / FAILURE
```

### Celery Beat (Scheduler)

```
Celery Beat (database namespace)
    | DatabaseScheduler (Django DB)
    | Tick periodico
    v
Redis Broker -> Celery Worker -> Task Execution
```

---

## 7. Stack Observability

```
                    APPLICATION LAYER
    +------------------------------------------+
    |  Django    Scrapy    Celery    Airflow    |
    |     |        |         |         |       |
    |     +--------+---------+---------+       |
    |              OTLP (gRPC :4317)           |
    +------------------+-----------------------+
                       v
              OTEL Collector (DaemonSet)
              +--------+--------+
              v        v        v
          Prometheus  Tempo   spanmetrics
          (metriche)  (trace) (trace->metrics)
              |        |
              v        v         Loki <-- Promtail (DaemonSet)
           +-------------------------+
           |       GRAFANA           |  (in-cluster + micro-monitor VM)
           |  Dashboards unificati   |
           |  Metriche + Log + Trace |
           |  + OCI Monitoring       |
           +-------------------------+
```

### Metriche Raccolte

| Sorgente | Metriche |
|----------|----------|
| django-prometheus | HTTP latency, status codes, DB queries |
| redis-exporter | Memory, connections, commands/sec |
| celery-exporter | Task duration, queue depth, failures |
| kube-state-metrics | Pod state, deployments, resource usage |
| node-exporter | CPU, RAM, disk, network per nodo |
| Kong prometheus | API latency/rate per route/consumer |
| OTEL spanmetrics | Trace-derived: p50/p95/p99 latency |

### Alertmanager

- **Namespace**: monitoring (nodeSelector: light)
- **Funzione**: Deduplicazione e routing alert da Prometheus
- **Receiver**: Configurabile (email, webhook, Slack)

---

## 8. CI/CD Pipeline

```
Developer
    | git push
    v
GitHub Repo
    | webhook
    v
Tekton Pipeline (k8s)
    +-- git-clone (Task)
    +-- kaniko-build (Task) -> ARM64 image
    +-- push to OCIR (eu-milan-1.ocir.io)
    |
    v
OCIR (Private Registry)
    | imagePullSecret: ocir-secret
    v
ArgoCD (GitOps)
    | watches k8s/ manifests in Git
    | auto-sync cluster state
    v
Rolling Update (zero-downtime)
    | maxSurge=1, maxUnavailable=0
    v
New Pod Running
```

### Componenti CI/CD

| Tool | Namespace | Ruolo |
|------|-----------|-------|
| Tekton Pipelines | tekton-pipelines | Build + push immagini |
| Kaniko | (Tekton task) | Build container senza Docker daemon |
| ArgoCD | clusters | GitOps delivery, sync Git -> cluster |
| SonarQube | devs | Code quality e security analysis |

---

## 9. Security Layers

| Layer | Tecnologia | Cosa protegge |
|-------|------------|---------------|
| **Network** | OCI Security Lists, VCN isolation | Traffico inter-subnet |
| **VPN** | WireGuard (micro-gw + k8s) | Accesso remoto sicuro al cluster |
| **TLS** | cert-manager + Let's Encrypt | HTTPS per tutti i sottodomini |
| **Ingress Auth** | OAuth2 Proxy (Google SSO) | Dashboard e tool senza auth nativa |
| **API Auth** | OAuth2 Client Credentials (DRF) | API esterne (scraper -> backoffice) |
| **API Gateway** | Kong (rate-limit, OIDC, CORS) | Protezione API da abusi |
| **mTLS** | Linkerd (opt-in per namespace) | Crittografia pod-to-pod |
| **Policy** | Kyverno | No privileged, no :latest, resource limits |
| **Registry** | OCIR private + imagePullSecret | Solo immagini autorizzate |
| **Secrets** | Ansible Vault + K8s Secrets | Credenziali criptate |
| **Backup** | Velero -> OCI Object Storage | DR: daily (7d) + weekly (30d) |

### Autenticazione per Servizio

| Servizio | Metodo Auth |
|----------|-------------|
| API esterne (scraper) | OAuth2 Client Credentials (token + scope) |
| Django Admin | Session + OAuth2Proxy SSO (Google) |
| Grafana | Auth nativa (admin password) |
| ArgoCD | Auth nativa (admin password) |
| Konga, Backstage, Traefik Dashboard | OAuth2 Proxy (Google SSO) via Traefik middleware |
| MinIO Console | OAuth2 Proxy (Google SSO) |
| MinIO API (S3) | Access Key / Secret Key |
| Kong Admin API | Solo accesso interno (ClusterIP) |

---

## 10. Backup e Disaster Recovery

```
K8s Cluster (etcd, PVC, resources)
    |
    v
Velero (clusters namespace)
    |
    +-- daily-full-backup    (02:00 UTC, retention 7 giorni)
    |   namespaces: database, apps, monitoring
    |
    +-- weekly-cluster-backup (domenica 03:00, retention 30 giorni)
        scope: intero cluster
    |
    v
OCI Object Storage (S3-compatible)
    bucket: velero-backups
    endpoint: *.compat.objectstorage.eu-milan-1.oraclecloud.com

RESTORE:
    velero restore create --from-backup <backup-name>
```

---

## 11. Database Condiviso — Mappa Utenze

```
PostgreSQL 16 + PostGIS 3.4 (database namespace, heavy node)
    |
    +-- DB: today_events  | User: events    | -> Backoffice Django
    +-- DB: kong          | User: kong      | -> Kong API Gateway
    +-- DB: konga         | User: konga     | -> Konga Admin UI
    +-- DB: airflow       | User: airflow   | -> Apache Airflow
    +-- DB: sonarqube     | User: sonarqube | -> SonarQube
    +-- DB: backstage     | User: backstage | -> Backstage
```

### Redis — Allocazione Database

| DB | Uso |
|----|-----|
| 0 | Airflow |
| 1 | Celery broker |
| 2 | Django cache |
| 5 | OAuth2Proxy sessions |

### MinIO — Object Storage S3-compatible

| Accesso | URL |
|---------|-----|
| API S3 (interno) | `http://minio.database.svc:9000` |
| API S3 (esterno) | `https://s3.oci.santocaruso.eu` |
| Console (esterno) | `https://minio.oci.santocaruso.eu` |

---

## 12. API Gateway — Kong

```
Traefik (TLS + host routing)
    |
    +-- api.oci.santocaruso.eu -> Kong (apps:8000)
                                    |
                              +-----+-----+
                              |  PLUGINS  |
                              |-----------|
                              | rate-limit|
                              | oauth2    |
                              | prometheus|
                              | cors      |
                              | http-log  |
                              +-----------+
                                    |
                                    v
                              Backoffice Django (apps:8000)

Kong Admin API: http://kong-kong-admin.apps.svc:8001 (solo interno)
Konga Admin UI: https://konga.oci.santocaruso.eu (Google SSO)
```

---

## 13. API Endpoints

### API Esterne (OAuth2 — via Kong)

| Endpoint | Metodo | Scopo | Response |
|----------|--------|-------|----------|
| `/api/external/v1/staging/` | GET | Lista staging events | 200 |
| `/api/external/v1/staging/` | POST | Crea singolo evento | 201/400 |
| `/api/external/v1/staging/bulk/` | POST | Bulk create (sync/async) | 201/202/400 |
| `/api/external/v1/staging/bulk-status/{task_id}/` | GET | Status task asincrono | 200 |
| `/api/external/v1/staging/clear_source/` | DELETE | Elimina per source | 200/400 |

### API Interne (Session)

| Endpoint | Metodo | Scopo |
|----------|--------|-------|
| `/api/events/` | CRUD | Production events |
| `/api/staging/` | GET | Staging events (read-only) |
| `/api/dashboard/` | GET | Statistiche aggregate |
| `/api/cms/citta/{slug}/` | GET | Pagine citta (CMS) |
| `/api/comuni-istat/` | GET | Comuni con dati geografici |
| `/docs/` | GET | Swagger UI (drf-spectacular) |
| `/docs/redoc/` | GET | ReDoc documentation |

---

## 14. Risorse per Nodo

### Heavy Node (3 OCPU / 18GB RAM)

| Servizio | Namespace | CPU req/lim | RAM req/lim |
|----------|-----------|-------------|-------------|
| PostgreSQL | database | 100m / 800m | 256Mi / 1Gi |
| Redis | database | 50m / 200m | 64Mi / 128Mi |
| MinIO | database | 100m / 500m | 256Mi / 512Mi |
| Celery Worker | database | 200m / 1000m | 512Mi / 768Mi |
| Celery Beat | database | 50m / 200m | 128Mi / 256Mi |
| Backoffice Django | apps | 100m / 500m | 256Mi / 512Mi |
| Kong | apps | 100m / 500m | 256Mi / 384Mi |
| Prometheus | monitoring | 50m / 500m | 128Mi / 512Mi |
| Grafana | monitoring | 50m / 250m | 128Mi / 256Mi |
| OTEL Collector | monitoring | 50m / 200m | 64Mi / 128Mi |
| SonarQube | devs | 100m / 500m | 768Mi / 1536Mi |
| Airflow Webserver | airflow | 200m / 1000m | 512Mi / 768Mi |
| Airflow git-sync | airflow | 50m / 100m | 64Mi / 128Mi |
| Airflow Scheduler | airflow | 100m / 500m | 256Mi / 512Mi |
| Airflow git-sync | airflow | 50m / 100m | 64Mi / 128Mi |
| **TOTALE** | | **1.4 / 6.85** | **3.7Gi / 7.5Gi** |

Utilizzo: requests 23% CPU, 23% RAM — limits 43% CPU, 47% RAM

### Light Node (1 OCPU / 6GB RAM)

| Servizio | Namespace | CPU req/lim | RAM req/lim |
|----------|-----------|-------------|-------------|
| Traefik | traefik | 50m / 300m | 64Mi / 256Mi |
| cert-manager | cert-manager | 10m / 100m | 32Mi / 128Mi |
| OAuth2 Proxy | traefik | 10m / 100m | 32Mi / 64Mi |
| metrics-server | kube-system | 10m / 100m | 32Mi / 128Mi |
| K8s Dashboard (Kong) | clusters | 10m / 100m | 32Mi / 128Mi |
| Alertmanager | monitoring | 10m / 100m | 32Mi / 128Mi |
| Loki | monitoring | 10m / 250m | 64Mi / 256Mi |
| Tempo | monitoring | 50m / 250m | 128Mi / 256Mi |
| WireGuard | wireguard | 50m / 200m | 64Mi / 128Mi |
| Velero | clusters | 50m / 500m | 128Mi / 512Mi |
| Velero UI | clusters | 50m / 200m | 128Mi / 256Mi |
| Konga | apps | 50m / 200m | 128Mi / 256Mi |
| redis-exporter | database | 10m / 50m | 32Mi / 64Mi |
| celery-exporter | database | 10m / 50m | 32Mi / 64Mi |
| Backstage | devs | 100m / 500m | 192Mi / 384Mi |
| Linkerd identity | linkerd | 10m / 100m | 32Mi / 128Mi |
| Linkerd destination | linkerd | 10m / 100m | 32Mi / 128Mi |
| Linkerd proxy-injector | linkerd | 10m / 100m | 32Mi / 128Mi |
| Linkerd Viz dashboard | linkerd-viz | 10m / 100m | 32Mi / 128Mi |
| Linkerd Viz metrics-api | linkerd-viz | 10m / 100m | 32Mi / 128Mi |
| Linkerd Viz tap | linkerd-viz | 10m / 100m | 32Mi / 128Mi |
| Linkerd Viz tap-injector | linkerd-viz | 10m / 100m | 32Mi / 128Mi |
| **TOTALE** | | **0.60 / 3.6** | **1.35Gi / 3.97Gi** |

Utilizzo: requests 12% CPU, 27% RAM — limits 72% CPU, 79% RAM

---

## 15. Ordine Deploy (Playbook Ansible)

```bash
# 1. Infrastruttura OCI (Terraform)
terraform apply
./scripts/get-kubeconfig.sh

# 2. Cluster base
ansible-playbook ansible/playbooks/post-cluster-setup.yml --ask-vault-pass
#   -> namespaces, OCIR secrets, cert-manager, metrics-server, K8s Dashboard

# 3. Ingress + Auth
ansible-playbook ansible/playbooks/traefik-setup.yml --ask-vault-pass
ansible-playbook ansible/playbooks/domain-setup.yml --ask-vault-pass
#   -> Traefik, OAuth2 Proxy, IngressRoutes

# 4. Database layer
kubectl apply -k k8s/postgres/
kubectl apply -k k8s/redis/

# 5. Object Storage
ansible-playbook ansible/playbooks/minio-setup.yml --ask-vault-pass

# 6. Servizi applicativi
ansible-playbook ansible/playbooks/kong-setup.yml --ask-vault-pass
ansible-playbook ansible/playbooks/backstage-setup.yml --ask-vault-pass
ansible-playbook ansible/playbooks/sonarqube-setup.yml --ask-vault-pass
ansible-playbook ansible/playbooks/airflow-setup.yml --ask-vault-pass

# 7. Monitoring
ansible-playbook ansible/playbooks/monitoring-setup.yml --ask-vault-pass
ansible-playbook ansible/playbooks/grafana-setup.yml --ask-vault-pass

# 8. Security + Mesh (opzionali)
ansible-playbook ansible/playbooks/security-setup.yml --ask-vault-pass
ansible-playbook ansible/playbooks/linkerd-setup.yml --ask-vault-pass

# 9. Backup + CI/CD
ansible-playbook ansible/playbooks/backup-setup.yml --ask-vault-pass

# 10. VPN + Reverse Proxy
ansible-playbook ansible/playbooks/wireguard-setup.yml --ask-vault-pass
ansible-playbook ansible/playbooks/reverse-proxy-setup.yml --ask-vault-pass
```

---

## 16. Punti di Forza

- **Costo zero** — Tutto su OCI Free Tier, nessun costo ricorrente
- **Osservabilita completa** — Metriche + Log + Trace unificati in Grafana
- **GitOps** — ArgoCD + Tekton per deploy automatici zero-downtime
- **Security multi-layer** — VPN, OAuth2, mTLS, Kyverno, HTTPS ovunque
- **Resilienza** — Backup automatici Velero, Celery retry, UPSERT dedup
- **Separation of concerns** — Kong per API cross-cutting, Django per business logic
- **Infrastructure as Code** — Terraform + Ansible + Kustomize, tutto versionato in Git

---

## 17. Criticita e Rischi

| Rischio | Impatto | Mitigazione |
|---------|---------|-------------|
| Single replica PostgreSQL/Redis | Downtime su crash nodo | Velero backup giornaliero, PVC persistente |
| RAM heavy node (18GB) | OOM killer su carico picco | Resource limits espliciti, monitoring alert |
| No HPA configurato | Nessun autoscaling su carico | metrics-server installato, HPA configurabile |
| Kyverno disabilitato di default | Policy non enforced | Abilitare con `install_kyverno: true` |
| Alcune immagini :latest | Deploy non deterministici | Pinnare tag in tutti i deployment |
| Micro VM 1GB RAM | Grafana al limite memoria | Monitorare con Uptime Kuma |
| No HA per control plane | OKE BASIC = single CP | Limite Free Tier, accettabile per il progetto |

---

## 18. Evoluzione Futura

| Area | Possibile evoluzione |
|------|----------------------|
| **Autoscaling** | Configurare HPA per backoffice e celery worker |
| **HA Database** | PostgreSQL replica read-only (se si esce dal Free Tier) |
| **Kong Dev Portal** | Developer Portal con Swagger self-service (Enterprise) |
| **Backstage plugin** | api-docs plugin per Swagger integrato nel catalogo |
| **MLflow + MinIO** | ML pipeline per classificazione automatica eventi |
| **Superset** | Dashboard BI per analisi eventi per citta/categoria |
| **Multi-region** | Replica cluster in altra region OCI per DR |
