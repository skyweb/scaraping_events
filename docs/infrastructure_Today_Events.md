# Infrastructure - Today Events

## Sviluppo locale (`docker-compose.dev.yml`)

Stack Docker con **Traefik v3.3** come reverse proxy HTTPS (certificati mkcert locali) e **subdomain routing** (`nomeservizio.${DOMAIN}`).

- **PostgreSQL 16** con PostGIS 3.4 — database principale
- **Redis 7** — cache e message broker Celery
- **Django + Celery** — backoffice, worker, beat, flower
- **React + Vite** — frontend dev server
- **Traefik v3.3** — reverse proxy HTTPS, subdomain routing, metriche Prometheus
- **Keycloak** — SSO / Identity Provider (OIDC), ForwardAuth e session store Redis
- **Grafana · Loki · Prometheus · Jaeger** — observability (log, metriche, tracing)
- **OpenTelemetry Collector** — raccolta e routing telemetry OTLP
- **Apache Superset** — BI dashboard eventi
- **Apache Airflow** — orchestrazione DAG (scraping, import comuni)
- **APISIX 3.x** — API Gateway (DB mode su PostgreSQL)
- **MinIO** — object storage S3-compatible
- **n8n** — workflow automation
- **SonarQube** — code quality e security analysis
- **Backstage** — developer portal
- **Scrapyd** — daemon spider (compose separato in `microservices/scraping-service/`)

## Servizi

### Applicativi (tutti via Traefik — HTTPS subdomain)

| Servizio | Sottodominio | Descrizione |
|----------|-------------|-------------|
| Frontend React + Vite | `frontend.${DOMAIN}` | SPA frontend, dev server Vite (porta 5173) |
| Backoffice API | `backoffice.${DOMAIN}/api/` | DRF REST API eventi |
| Django Admin | `backoffice.${DOMAIN}/admin/` | Pannello admin Unfold (protetto ForwardAuth) |
| OAuth2 | `backoffice.${DOMAIN}/o/` | Token endpoint client credentials |
| Flower | `flower.${DOMAIN}` | UI monitoraggio task Celery |
| Grafana | `grafana.${DOMAIN}` | Dashboard log, metriche, traces |
| Jaeger | `jaeger.${DOMAIN}` | UI distributed tracing con Monitor/SPM |
| Prometheus | `prometheus.${DOMAIN}` | Query metriche time-series |
| Superset | `superset.${DOMAIN}` | BI dashboard eventi |
| Airflow | `airflow.${DOMAIN}` | Orchestrazione DAG |
| Keycloak | `keycloak.${DOMAIN}` | Identity Provider SSO (OIDC/OAuth2) |
| APISIX Dashboard | `apisix.${DOMAIN}` | Admin UI API Gateway |
| APISIX Proxy | `gateway.${DOMAIN}` | API Gateway proxy |
| MinIO Console | `minio.${DOMAIN}` | UI gestione object storage |
| MinIO S3 API | `s3.${DOMAIN}` | API S3-compatible |
| n8n | `n8n.${DOMAIN}` | Workflow automation |
| SonarQube | `sonarqube.${DOMAIN}` | Code quality analysis |
| Backstage | `backstage.${DOMAIN}` | Developer portal |
| Traefik Dashboard | `traefik.${DOMAIN}` | Dashboard reverse proxy |

### Infrastruttura

| Servizio | Porta | Descrizione |
|----------|-------|-------------|
| Traefik v3.3 | `:80` `:443` `:8082` | Reverse proxy HTTPS, subdomain routing, metriche Prometheus |
| docker-api-proxy | — | Nginx proxy per Docker socket (fix API version per Docker Desktop 4.62+) |
| Keycloak | — | SSO OIDC, ForwardAuth, session store Redis (DB 5) |
| auth-redirect | — | Pagina statica JS redirect per intercettare 401 Traefik |
| PostgreSQL + PostGIS | `:5432` | Database principale con estensioni geospaziali (include schema Keycloak) |
| Redis | `:6379` | Cache sessioni (DB 0-2), broker Celery, session Keycloak (DB 5) |
| Celery Worker | — | Esecuzione task asincroni (es. `process_bulk_events`) |
| Celery Beat | — | Scheduler task periodici (usa `django_celery_beat`) |
| Airflow Scheduler | — | Esecuzione DAG (LocalExecutor su PostgreSQL) |
| Scrapyd | `:6800` (int.) | Daemon Scrapy — scheduling spider via HTTP API |

### Observability

| Servizio | Porta | Descrizione |
|----------|-------|-------------|
| Grafana 11.1 | `:3001` | Dashboard unificata: log (Loki), metriche (Prometheus), traces (Jaeger) |
| Jaeger v2 | `:16686` | UI distributed tracing con Monitor/SPM (in-memory, 100K traces) |
| Prometheus | `:9090` | Storage e query metriche time-series (retention 1 giorno) |
| Loki 3.1 | `:3100` | Backend aggregazione e query log (retention 24h) |
| OpenTelemetry Collector | `:4317` gRPC · `:4318` HTTP | Raccolta e routing telemetry OTLP |
| Promtail | — | Collector log dai container Docker → Loki (filtra solo `dev-*`) |
| Redis Exporter | `:9121` | Metriche Redis → Prometheus |
| Celery Exporter | `:9808` | Metriche task Celery → Prometheus |

#### Prometheus scrape jobs (dev)

| Job | Target | Intervallo |
|-----|--------|-----------|
| `otel-collector` | `otel-collector:8889` | 15s |
| `jaeger-spanmetrics` | `jaeger:8889` | 15s |
| `django` | `backoffice:8000` | 15s |
| `redis` | `redis-exporter:9121` | 15s |
| `celery` | `celery-exporter:9808` | 15s |
| `traefik` | `traefik:8080` | 15s |
| `apisix` | `apisix:9091` | 15s |

#### Grafana datasources (dev)

- **Prometheus** (default) — metriche
- **Loki** — log (con derived field per Jaeger traceID)
- **Jaeger** — traces

#### Grafana dashboards (dev)

| Cartella | Dashboard |
|----------|-----------|
| Health | `services-health.json`, `service-detail.json` |
| Application | `celery-exporter.json`, `django-logs.json`, `django-prometheus.json` |
| Infrastructure | `redis-exporter.json` |

#### Instrumentazione applicativa (OpenTelemetry)

Django, Celery Worker e Celery Beat inviano telemetry via OTLP al collector. Instrumentazioni abilitate:

- Django (HTTP), Celery (task), Requests (outbound HTTP), SQLAlchemy (DB), Redis (cache)
- Log correlation: `otelTraceID`, `otelSpanID`, `otelServiceName` iniettati in ogni log record

| Service Name | Container |
|-------------|-----------|
| `backoffice-django` | `dev-backoffice` |
| `backoffice-celery-worker` | `dev-backoffice-celery-worker` |
| `backoffice-celery-beat` | `dev-backoffice-celery-beat` |

### Business Intelligence

| Servizio | Porta | Descrizione |
|----------|-------|-------------|
| Apache Superset 4.0 | `:8088` | Dashboard BI con datasource pre-configurato su `events_data` |

### Orchestrazione DAG

| Servizio | Porta | Descrizione |
|----------|-------|-------------|
| Apache Airflow 2.9 Webserver | `:8080` | UI scheduling e monitoraggio DAG |
| Apache Airflow Scheduler | — | Esecuzione DAG (LocalExecutor su PostgreSQL) |

### API Gateway

| Servizio | Porta | Descrizione |
|----------|-------|-------------|
| APISIX 3.x | `:9080` proxy · `:9180` admin API · `:9000` dashboard | API Gateway DB mode su PostgreSQL, autenticazione via plugin OIDC (Keycloak) |

## Accesso (dev)

Tutti i servizi protetti da ForwardAuth usano OIDC via Keycloak. I JWT emessi da Keycloak vengono verificati da APISIX tramite il plugin OIDC. Il flusso è: **Traefik → APISIX → Django** con Keycloak come Identity Provider.

| Servizio | URL | Auth |
|----------|-----|------|
| Frontend | `https://frontend.${DOMAIN}` | Nessuna |
| Backoffice API | `https://backoffice.${DOMAIN}/api/` | JWT (client credentials via Keycloak) |
| Django Admin | `https://backoffice.${DOMAIN}/admin/` | ForwardAuth (Keycloak OIDC) |
| Flower | `https://flower.${DOMAIN}` | ForwardAuth |
| Grafana | `https://grafana.${DOMAIN}` | ForwardAuth (anonymous Admin) |
| Jaeger | `https://jaeger.${DOMAIN}` | ForwardAuth |
| Prometheus | `https://prometheus.${DOMAIN}` | ForwardAuth |
| Superset | `https://superset.${DOMAIN}` | ForwardAuth · `admin` / vedi `.env` |
| Airflow | `https://airflow.${DOMAIN}` | ForwardAuth · `admin` / vedi `.env` |
| Keycloak | `https://keycloak.${DOMAIN}` | Nessuna (login interno) |
| APISIX Dashboard | `https://apisix.${DOMAIN}` | ForwardAuth |
| MinIO Console | `https://minio.${DOMAIN}` | ForwardAuth · `minioadmin` / vedi `.env` |
| n8n | `https://n8n.${DOMAIN}` | ForwardAuth |
| SonarQube | `https://sonarqube.${DOMAIN}` | Nessuna (login interno) |
| Backstage | `https://backstage.${DOMAIN}` | ForwardAuth (guest auth abilitata) |
| Traefik | `https://traefik.${DOMAIN}` | ForwardAuth |

`DOMAIN` si imposta in `infrastructures/.env` (default: `127.0.0.1.nip.io`).

In produzione l'endpoint auth è esposto su `https://auth.${DOMAIN}`.

## Struttura Directory

```
infrastructures/
├── docker-compose.dev.yml     # Stack dev completo (HTTPS mkcert)
├── docker-compose.prod.yml    # Stack produzione (HTTPS — Let's Encrypt)
├── .env                       # Variabili d'ambiente (non in git)
├── .env.example               # Template variabili
├── Makefile                   # Comandi rapidi (make up, make logs-*, ...)
├── logs/                      # Log runtime (montati dai container)
├── OCI/                       # Infrastruttura Oracle Cloud (Kubernetes)
│   ├── ansible/               # Playbook Ansible per deploy
│   └── k8s/                   # Manifest e Helm values Kubernetes
│       └── monitoring/        # Stack monitoring OCI/OKE
└── services/                  # Configurazioni per servizio
    ├── airflow/               # DAG, plugin, dags/, data/, logs/
    ├── apisix/                # apisix.yaml, config.yaml (plugin OIDC, route, upstream)
    ├── auth-redirect/         # index.html JS redirect per 401
    ├── docker-proxy/          # nginx.conf proxy Docker socket
    ├── grafana/               # Provisioning datasource + dashboard + alerting
    ├── jaeger/                # jaeger-v2-config.yaml, ui-config.json
    ├── keycloak/              # realm export, client config, theme
    ├── loki/                  # loki-config.yaml
    ├── otel-collector/        # otel-collector-config.yaml
    ├── postgres/              # init SQL (schema PostGIS, schema Keycloak)
    ├── prometheus/            # prometheus.yml
    ├── promtail/              # promtail-config.yaml
    ├── superset/              # superset_config.py + init.sh + assets/
    └── traefik/               # dynamic.yml + certs/ (mkcert)
```

## Produzione OCI — Kubernetes (OKE)

Infrastruttura su Oracle Cloud con Kubernetes (OKE), gestita via Ansible e Helm.

### Stack monitoring OCI/OKE

| Componente | Tipo | Descrizione |
|------------|------|-------------|
| Prometheus | Helm `prometheus-community/prometheus` | Metriche, retention 7d, 10Gi PV |
| Grafana | Helm `grafana/grafana` | UI unificata, proxy auth OIDC, plugin OCI Logs |
| Loki | Helm `grafana/loki` (SingleBinary) | Log backend, retention 168h |
| Promtail | Helm `grafana/promtail` (DaemonSet) | Collector log CRI |
| Tempo | Helm `grafana/tempo` (SingleBinary) | Trace backend, metrics generator, retention 168h |
| OTEL Collector | Helm `open-telemetry/opentelemetry-collector` (DaemonSet) | OTLP receiver, spanmetrics, remote write |
| Redis Exporter | K8s Deployment | Metriche Redis (namespace `database`) |
| Celery Exporter | K8s Deployment | Metriche Celery (namespace `database`) |
| PostgreSQL Exporter | Helm `prometheus-postgres-exporter` | Metriche PostgreSQL |

### Prometheus scrape jobs (OKE)

| Job | Target | Descrizione |
|-----|--------|-------------|
| `otel-spanmetrics` | `otel-collector...monitoring.svc:8889` | Span metrics da OTEL Collector |
| `django` | `backoffice.apps.svc:8000` | Metriche applicazione Django |
| `redis-exporter` | `redis-exporter.database.svc:9121` | Metriche Redis |
| `celery-exporter` | `celery-exporter.database.svc:9808` | Metriche task Celery |
| `apisix` | `apisix.apps.svc:9091` | Metriche API Gateway |
| `postgres-exporter` | `postgres-exporter...monitoring.svc:80` | Metriche PostgreSQL |
| `kubelet-cadvisor` | Auto-discovery nodi (`role: node`) | Metriche container/pod da kubelet `/metrics/cadvisor` |

Componenti abilitati dal chart Prometheus:
- **kube-state-metrics** — stato oggetti K8s (pod, deployment, node)
- **prometheus-node-exporter** — metriche hardware/OS di ogni nodo

### Grafana datasources (OKE)

- **Prometheus** (default) — metriche
- **Loki** — log
- **Tempo** — traces (con link a Loki e Prometheus, service map, node graph)
- **PostgreSQL** — query dirette su DB `events`
- **OCI Logs** — log Oracle Cloud

### Grafana dashboards (OKE)

| Cartella | Dashboard | ID |
|----------|-----------|----|
| Kubernetes | Views / Global | 15760 |
| Kubernetes | Views / Namespaces | 15757 |
| Kubernetes | Views / Nodes | 15758 |
| Kubernetes | Views / Pods | 15759 |
| Kubernetes | Deployments / StatefulSet / DaemonSet | 8685 |
| Kubernetes | Persistent Volumes | 13646 |
| Infrastructure | Node Exporter Full | 1860 |
| Database | PostgreSQL Database | 9628 |

### Deploy monitoring OKE

```bash
cd infrastructures/OCI/ansible
ansible-playbook playbooks/monitoring-setup.yml
```

Il playbook crea secrets K8s, installa tutti gli Helm chart e applica il manifest Kustomize.

## Produzione (HTTPS — Let's Encrypt)

Lo stack di produzione usa `docker-compose.prod.yml` con Traefik che gestisce certificati SSL automatici via Let's Encrypt (ACME HTTP-01).

### Prerequisiti

1. **DNS**: wildcard `*.tuodominio.com` -> IP del server (oppure un A record per ogni sottodominio)
2. **Firewall**: porte 80 e 443 aperte (80 serve per il challenge ACME anche se tutto il traffico viene rediretto a 443)
3. **`.env`**: configurare `DOMAIN` con il dominio reale e `ACME_EMAIL` con un'email valida
4. **Keycloak**: aggiornare il redirect URI nel realm Keycloak a `https://auth.DOMAIN/callback`

### Avvio

```bash
cd infrastructures

# Configurare .env
DOMAIN=events.example.com
ACME_EMAIL=admin@example.com

# Avviare
make prod-up

# Verificare stato
make prod-ps

# Logs
make prod-logs
```

### Differenze rispetto al dev

| Aspetto | Dev (`docker-compose.dev.yml`) | Prod (`docker-compose.prod.yml`) |
|---------|-------------------------------|----------------------------------|
| Protocollo | HTTPS (mkcert, certificati locali trusted) | HTTPS (Let's Encrypt automatici) |
| Django | `runserver` + volume mount + DEBUG=True | `gunicorn` + immagine build + DEBUG=False |
| Frontend | Vite dev server (porta 5173) | Build statico nginx (porta 80) |
| Cookie Keycloak | `secure=true` | `secure=true` |
| Cookie n8n | `secure=false` | `secure=true` |
| Traefik dashboard | Esposto su porta 8082 (insecure) | Solo via router autenticato HTTPS |
| Container prefix | `dev-*` | `prod-*` |
| Volumi | `dev-*` | `prod-*` + volume `acme-data` |
| Rete | `dev-network` | `prod-network` |
| Auth endpoint | `keycloak.${DOMAIN}` | `auth.${DOMAIN}` |

### Primo avvio e certificati

Al primo avvio, Traefik richiede i certificati per tutti i sottodomini. Questo può richiedere 30-60 secondi. I certificati vengono salvati nel volume `prod-acme-data` e rinnovati automaticamente.

Per testare senza consumare rate limit Let's Encrypt, aggiungere temporaneamente al comando Traefik in `docker-compose.prod.yml`:
```yaml
- --certificatesresolvers.letsencrypt.acme.caserver=https://acme-staging-v02.api.letsencrypt.org/directory
```

## Note

### Rete Docker

Tutti i servizi sono collegati alla rete bridge `dev-network`.
Il compose Scrapyd (`microservices/scraping-service/docker-compose.yml`) usa la stessa rete.
