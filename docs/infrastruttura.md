# Infrastruttura Today Events

## Panoramica

```
Browser (HTTPS *.127.0.0.1.nip.io)
   │
   ▼
APISIX 3.15 (TLS termination, OIDC SSO, rate-limit, CORS, WAF, tracing)
   │              │
   │              └──► Keycloak 26 (IdP — SSO, OIDC, OAuth2)
   │                       │
   │                       └──► PostgreSQL 16 (db: keycloak)
   ▼
Django Backoffice (Unfold Admin, DRF API, Report)
   │         │
   │         ├──► PostgreSQL 16 + PostGIS (db: today_events)
   │         └──► Redis 7 (cache, Celery broker)
   ▼
Celery Worker
   │
   ▼
Airflow 2.9 (orchestrazione DAG scraping)
   │
   ▼
OpenTelemetry Collector
   ├──► Grafana Tempo 2.9 (traces)
   ├──► Prometheus (metriche)
   └──► Loki 3.6 + Alloy 1.14 (log)
          └──► Grafana 12.3 (dashboard unificata)
```

---

## Servizi

### Applicazione

| Servizio | Immagine | Porta | Dominio dev |
|---|---|---|---|
| Django Backoffice | custom (`python:3.11-slim`) | 8000 | `backoffice.${DOMAIN}` |
| Celery Worker | stessa immagine backoffice | — | — |
| Flower | `mher/flower:2.0` | 5555 | `flower.${DOMAIN}` |
| Airflow Webserver | `apache/airflow:2.9.2` | 8080 | `airflow.${DOMAIN}` |
| Airflow Scheduler | `apache/airflow:2.9.2` | — | — |

### Autenticazione

| Servizio | Immagine | Porta | Dominio dev |
|---|---|---|---|
| Keycloak | `quay.io/keycloak/keycloak:26.0` | 8080 | `auth.${DOMAIN}` |

### Infrastruttura

| Servizio | Immagine | Porta | Dominio dev |
|---|---|---|---|
| APISIX | `apache/apisix:3.15.0-ubuntu` | 9443 (HTTPS) | `*.${DOMAIN}` (entry point unico) |
| APISIX Dashboard | `apache/apisix-dashboard:3.0.1-alpine` | 9000 | `apisix-dashboard.${DOMAIN}` |
| etcd | `quay.io/coreos/etcd:v3.5.17` | 2379 | — |
| PostgreSQL + PostGIS | `imresamu/postgis:16-3.4` | 5432 | — |
| Redis | `redis:7-alpine` | 6379 | — |
| MinIO | `minio/minio:RELEASE.2025-04-22` | 9000/9001 | `minio.${DOMAIN}` |
| Mailpit | `axllent/mailpit:latest` | 8025 | `mail.${DOMAIN}` |
| Harbor Registry | compose separato | 443 | `registry.${DOMAIN}` |

### Observability

| Servizio | Immagine | Porta | Descrizione |
|---|---|---|---|
| Grafana | `grafana/grafana:12.3.0` | 3001 | Dashboard unificata (log, metriche, traces) |
| Prometheus | `prom/prometheus:v2.53.0` | 9090 | Metriche time-series |
| Loki | `grafana/loki:3.6.7` | 3100 | Log backend |
| Alloy | `grafana/alloy:1.14.1` | 12345 | Log collector (sostituto Promtail) |
| Tempo | `grafana/tempo:2.9.0` | 3200 | Trace backend |
| OTel Collector | `otel/opentelemetry-collector-contrib:0.104.0` | 4317 (gRPC), 4318 (HTTP) | Raccolta e routing telemetry OTLP |
| Redis Exporter | `oliver006/redis_exporter:latest` | 9121 | Metriche Redis → Prometheus |
| Celery Exporter | `danihodovic/celery-exporter:latest` | 9808 | Metriche Celery → Prometheus |

---

## APISIX — API Gateway (entry point unico)

APISIX è l'unico servizio esposto su HTTPS. Gestisce TLS termination con certificato wildcard mkcert (`*.127.0.0.1.nip.io`), autenticazione OIDC via Keycloak, rate-limiting, CORS, WAF (Coraza) e tracing.

Le route sono inizializzate da `services/apisix/init-routes.sh` all'avvio del container `apisix-init`.

### Route principali

| Host | Path | Auth | Upstream |
|---|---|---|---|
| `backoffice.${DOMAIN}` | `/admin/*` | OIDC SSO | Django (:8000) |
| `backoffice.${DOMAIN}` | `/api/v1/events/*` | JWT Bearer | Django (:8000) |
| `backoffice.${DOMAIN}` | `/api/*`, `/docs/*`, `/report/*` | Nessuna / Session | Django (:8000) |
| `webservice.${DOMAIN}` | `/api/external/*` | JWT Bearer (M2M) | Django (:8000) |
| `grafana.${DOMAIN}` | `/*` | OIDC SSO (auth proxy) | Grafana (:3001) |
| `airflow.${DOMAIN}` | `/*` | OIDC SSO (auth proxy + roles) | Airflow (:8080) |
| `prometheus.${DOMAIN}` | `/*` | OIDC SSO | Prometheus (:9090) |
| `flower.${DOMAIN}` | `/*` | OIDC SSO | Flower (:5555) |
| `auth.${DOMAIN}` | `/*` | Nessuna | Keycloak (:8080) |
| `apisix-dashboard.${DOMAIN}` | `/*` | OIDC SSO | APISIX Dashboard (:9000) |
| `minio.${DOMAIN}` | `/*` | Nessuna (auth interna) | MinIO (:9001) |
| `registry.${DOMAIN}` | `/*` | Nessuna (auth interna Harbor) | Harbor (:443) |
| `mail.${DOMAIN}` | `/*` | Nessuna (solo dev) | Mailpit (:8025) |

Plugin abilitati: `openid-connect`, `jwt-auth`, `consumer-restriction`, `limit-count`, `cors`, `prometheus`, `opentelemetry`, `proxy-rewrite`, `response-rewrite`, `serverless-pre-function`, `serverless-post-function`.

---

## Keycloak — Identity Provider

### Realm: `today-events`

Registrazione autonoma disabilitata (`registrationAllowed: false`). Social login configurabile (Google, GitHub).

### Ruoli realm

| Ruolo | Descrizione |
|---|---|
| `admin` | Amministratore completo (Django superuser, Airflow Admin) |
| `web` | Accesso Django Admin (gruppo Redazione, permessi limitati) |
| `monitoring` | Accesso Airflow (Viewer), Grafana, Prometheus, Flower |
| `api-consumer` | Consumatore API esterne (client credentials) |

### Client OIDC

| Client ID | Flow | Utilizzato da |
|---|---|---|
| `backoffice-admin` | Authorization Code | APISIX (SSO tutti i servizi web) |
| `scraper-service` | Client Credentials (M2M) | Scraping service → API |
| `minio-console` | Authorization Code | MinIO (OIDC login console) |
| `harbor` | Authorization Code | Harbor Registry (OIDC login UI) |
| `airflow-service` | Client Credentials (M2M) | Airflow DAG → API |

### Utenti creati al primo avvio

| Utente | Password | Ruoli |
|---|---|---|
| `admin` | `admin_secret_2026` | `admin`, `web`, `monitoring` |

### Endpoint principali

```
Discovery: /realms/today-events/.well-known/openid-configuration
Token:     /realms/today-events/protocol/openid-connect/token
JWKS:      /realms/today-events/protocol/openid-connect/certs
UserInfo:  /realms/today-events/protocol/openid-connect/userinfo
Logout:    /realms/today-events/protocol/openid-connect/logout
```

---

## Autenticazione — Flussi

### SSO Browser (OIDC via APISIX)

Tutti i servizi web (Django Admin, Grafana, Airflow, Prometheus, Flower, APISIX Dashboard) sono protetti dal plugin `openid-connect` di APISIX. Il flusso è descritto in dettaglio in [`docs/SSO.md`](SSO.md).

### Client Credentials (M2M)

Usato da Scrapy spider e Airflow DAG per chiamare le API del backoffice.

```
1. POST /realms/today-events/protocol/openid-connect/token
   Body: grant_type=client_credentials&client_id=...&client_secret=...&scope=openid read write
   ← { access_token: "<JWT>", expires_in: 36000 }

2. POST https://webservice.${DOMAIN}/api/external/v1/staging/bulk/
   Authorization: Bearer <JWT>

3. APISIX → verifica JWT (JWKS) → proxy a Django
   Django → KeycloakJWTAuthentication (PyJWT, RS256, cache JWKS 5min)
```

---

## Database PostgreSQL

Tutti i servizi condividono lo stesso container PostgreSQL su database separati:

| Database | Usato da |
|---|---|
| `today_events` | Django Backoffice, Airflow (metadata) |
| `keycloak` | Keycloak (sessioni, realm, client) |
| `harbor` | Harbor Docker Registry |

Creati automaticamente da `services/postgres/init.d/02-databases.sql` al primo avvio.

### Redis

| DB | Usato da |
|---|---|
| 0 | Airflow Celery broker |
| 1 | Django Celery broker |
| 2 | Django cache |

---

## Observability

### Pipeline

| Tipo | Flusso |
|---|---|
| **Traces** | App (OTLP) → OTel Collector → Tempo → Grafana |
| **Metriche** | App (Prometheus endpoint) → Prometheus scrape → Grafana |
| **Log** | Container Docker → Alloy → Loki → Grafana |

### Prometheus scrape jobs

| Job | Target |
|---|---|
| `otel-collector` | `otel-collector:8889` |
| `django` | `backoffice:8000` |
| `redis` | `redis-exporter:9121` |
| `celery` | `celery-exporter:9808` |
| `apisix` | `apisix:9091` |
| `keycloak` | `keycloak:9000` |
| `keycloak-metrics-spi` | `keycloak:8080` |
| `alloy` | `alloy:12345` |

### Grafana datasources

| Datasource | Tipo | Default |
|---|---|---|
| Prometheus | Metriche | Si |
| Loki | Log | No |
| Tempo | Traces | No |

### Grafana dashboards provisionate

| Cartella | Dashboard |
|---|---|
| health | `services-health`, `service-detail`, `sla-uptime` |
| application | `django-prometheus`, `django-logs`, `celery-exporter`, `events-pipeline`, `business-kpi`, `api-usage`, `api-consumers`, `airflow-dags` |
| infrastructure | `redis-exporter`, `coraza-waf`, `harbor-registry`, `tempo-traces`, `alloy-logs` |
| (root) | `apisix`, `keycloak` |

### Instrumentazione OpenTelemetry

| Service Name | Container |
|---|---|
| `backoffice-django` | `dev-backoffice` |
| `backoffice-celery-worker` | `dev-backoffice-celery-worker` |

Instrumentazioni: Django (HTTP), Celery (task), Requests (outbound), SQLAlchemy (DB), Redis (cache).
Log correlation: `otelTraceID`, `otelSpanID`, `otelServiceName` iniettati in ogni log record.

### Alerting (Grafana provisioned)

| Gruppo | Alert |
|---|---|
| service-health | Servizio non raggiungibile |
| django | Admin errors 5xx, Error rate > 5%, Latenza P95 > 2s |
| redis | Memoria > 85%, Connessioni > 100 |
| celery | Task in errore, Coda > 50 task |
| apisix | Error rate > 5%, Latenza P95 > 3s |
| keycloak | Login falliti > 0.5/s, JVM heap > 85% |
| coraza-waf | Attacchi rilevati > 10/5min, Rate limit 429 |
| alloy | Non raggiungibile, Memoria > 256MB, Errori push Loki |

---

## Avvio

```bash
cd infrastructures

# Stack completo (tutti i servizi)
make up

# Solo core (senza observability e airflow)
make up-core

# Gruppi individuali
make up-observability
make up-airflow
make up-harbor
```

### Accesso dev

| URL | Servizio | Credenziali |
|---|---|---|
| `https://backoffice.${DOMAIN}/admin/` | Django Admin | SSO Keycloak (`admin` / `admin_secret_2026`) |
| `https://backoffice.${DOMAIN}/report/` | Report Dashboard | SSO (login required) |
| `https://backoffice.${DOMAIN}/docs/` | API Docs (interno) | — |
| `https://backoffice.${DOMAIN}/docs/public/` | API Docs (pubblico) | — |
| `https://auth.${DOMAIN}/` | Keycloak Admin Console | `admin` / `admin_secret_2026` (realm master) |
| `https://grafana.${DOMAIN}/` | Grafana | SSO Keycloak (auto sign-up) |
| `https://airflow.${DOMAIN}/` | Airflow | SSO Keycloak (ruolo `admin` o `monitoring`) |
| `https://prometheus.${DOMAIN}/` | Prometheus | SSO Keycloak |
| `https://flower.${DOMAIN}/` | Flower | SSO Keycloak |
| `https://apisix-dashboard.${DOMAIN}/` | APISIX Dashboard | SSO Keycloak |
| `https://minio.${DOMAIN}/` | MinIO Console | `minioadmin` / `minio_secret_2026` |
| `https://registry.${DOMAIN}/` | Harbor Registry | Auth interna Harbor |
| `https://mail.${DOMAIN}/` | Mailpit | Nessuna (solo dev) |

`DOMAIN` si configura in `infrastructures/.env` (default: `127.0.0.1.nip.io`).

---

## Struttura directory

```
infrastructures/
├── docker-compose.dev.yml        # Stack dev completo
├── .env                          # Variabili d'ambiente
├── Makefile                      # Comandi rapidi (make up, make logs-*, ...)
├── logs/                         # Log runtime
├── OCI/                          # Infrastruttura Oracle Cloud (Kubernetes)
│   ├── ansible/                  # Playbook Ansible
│   └── k8s/                      # Manifest e Helm values
└── services/                     # Configurazioni per servizio
    ├── airflow/                  # DAG, plugin, webserver_config.py
    ├── alloy/                    # config.alloy (log collector)
    ├── apisix/                   # config.yaml, init-routes.sh, certs/
    ├── grafana/                  # provisioning/, dashboards/, templates/
    ├── harbor/                   # docker-compose.yml, cosign keys
    ├── keycloak/                 # realm-today-events.json, themes/
    ├── loki/                     # loki-config.yaml
    ├── otel-collector/           # otel-collector-config.yaml
    ├── postgres/                 # init.d/ (extensions, databases), sql/
    ├── prometheus/               # prometheus.yml, alert-rules.yml
    ├── redis/                    # (config default)
    └── tempo/                    # tempo-config.yaml
```

---

## Rete Docker

Tutti i servizi sono sulla rete bridge `dev-network` (external).
Il compose Harbor (`services/harbor/docker-compose.yml`) e Scrapyd (`microservices/scraping-service/docker-compose.yml`) condividono la stessa rete.
