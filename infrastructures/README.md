# Infrastructure - Today Events

Stack Docker per lo sviluppo locale (`docker-compose.dev.yml`):
- **PostgreSQL 16** con PostGIS 3.4 — database principale
- **Redis 7** — cache e message broker Celery
- **Django + Celery** — backoffice, worker, beat, flower
- **React + Vite** — frontend dev server
- **Nginx** — reverse proxy su porta 80, espone tutti i servizi su `http://localhost`
- **Grafana · Loki · Prometheus · Jaeger** — observability (log, metriche, tracing)
- **Apache Superset** — BI dashboard eventi
- **Apache Airflow** — orchestrazione DAG (scraping, import comuni)
- **Scrapyd** — daemon spider (compose separato in `microservices/scraping-service/`)

## Servizi

### Applicativi (tutti via Nginx — http://localhost)

| Servizio | URL | Porta diretta | Descrizione |
|----------|-----|--------------|-------------|
| Frontend React + Vite | `http://localhost/` | `:3000` | SPA frontend, dev server Vite |
| Backoffice API | `http://localhost/api/` | `:8000` | DRF REST API eventi staging e production |
| Django Admin | `http://localhost/admin/` | `:8000` | Pannello admin Unfold |
| OAuth2 | `http://localhost/o/` | `:8000` | Token endpoint client credentials |
| Flower | `http://localhost/flower/` | — | UI monitoraggio task Celery |
| Grafana | `http://localhost/grafana/` | `:3001` | Dashboard log, metriche, traces |
| Jaeger | `http://localhost/jaeger/` | `:16686` | UI distributed tracing |
| Prometheus | `http://localhost/prometheus/` | `:9090` | Query metriche time-series |
| Superset | `http://localhost/superset/` | `:8088` | BI dashboard eventi |
| Airflow | `http://localhost/airflow/` | `:8080` | Orchestrazione DAG |
| Loki | `http://localhost/loki/` | `:3100` | API log backend |
| Redis Exporter | `http://localhost/redis-exporter/` | `:9121` | Metriche Redis |
| cAdvisor | `http://localhost/cadvisor/` | `:8081` | Metriche container Docker |

### Infrastruttura

| Servizio | Porta | Descrizione |
|----------|-------|-------------|
| Nginx | `:80` | Reverse proxy — entry point unico |
| PostgreSQL + PostGIS | `:5432` | Database principale con estensioni geospaziali |
| Redis | `:6379` | Cache sessioni e message broker per Celery |
| Celery Worker | — | Esecuzione task asincroni (es. `process_bulk_events`) |
| Celery Beat | — | Scheduler task periodici (usa `django_celery_beat`) |
| Airflow Scheduler | — | Esecuzione DAG Airflow |
| Scrapyd | `:6800` (int.) | Daemon Scrapy — scheduling spider via HTTP API |

### Observability

| Servizio | Porta | Descrizione |
|----------|-------|-------------|
| Grafana | `:3001` | Dashboard unificata: log (Loki), metriche (Prometheus), traces (Jaeger) |
| Jaeger | `:16686` | UI distributed tracing con Monitor/SPM |
| Prometheus | `:9090` | Storage e query metriche time-series |
| Loki | `:3100` | Backend aggregazione e query log |
| OpenTelemetry Collector | `:4317` gRPC · `:4318` HTTP | Raccolta e routing telemetry OTLP |
| Promtail | — | Collector log dai container Docker → Loki |
| Redis Exporter | `:9121` | Metriche Redis → Prometheus |
| Celery Exporter | `:9808` | Metriche task Celery → Prometheus |
| cAdvisor | `:8081` | Metriche risorse container Docker → Prometheus |

### Business Intelligence

| Servizio | Porta | Descrizione |
|----------|-------|-------------|
| Apache Superset | `:8088` | Dashboard BI con datasource pre-configurato su `events_data` |

### Orchestrazione DAG

| Servizio | Porta | Descrizione |
|----------|-------|-------------|
| Apache Airflow Webserver | `:8080` | UI scheduling e monitoraggio DAG |
| Apache Airflow Scheduler | — | Esecuzione DAG (LocalExecutor su PostgreSQL) |

## Accesso

| Servizio | URL | Credenziali |
|----------|-----|-------------|
| Frontend | `http://localhost/` | — |
| Django Admin | `http://localhost/admin/` | `admin` / vedi `.env` |
| Backoffice API | `http://localhost/api/` | OAuth2 client credentials |
| Flower | `http://localhost/flower/` | — |
| Grafana | `http://localhost/grafana/` | `admin` / `admin` (primo accesso) |
| Jaeger | `http://localhost/jaeger/` | — |
| Prometheus | `http://localhost/prometheus/` | — |
| Superset | `http://localhost/superset/` | `admin` / vedi `.env` |
| Airflow | `http://localhost/airflow/` | `admin` / `admin_secret_2026` |

## Struttura Directory

```
infrastructures/
├── docker-compose.dev.yml     # Stack dev completo
├── .env                       # Variabili d'ambiente (non in git)
├── .env.example               # Template variabili
├── Makefile                   # Comandi rapidi (make up, make logs-*, ...)
├── logs/                      # Log runtime (montati dai container)
└── services/                  # Configurazioni per servizio
    ├── airflow/               # DAG, plugin, dags/, logs/
    │   ├── DAG.md             # Documentazione DAG disponibili
    │   ├── dags/              # File DAG Python
    │   ├── data/              # Dataset per DAG
    │   ├── logs/              # Log Airflow
    │   └── plugins/           # Plugin custom Airflow
    ├── grafana/               # Provisioning datasource + dashboard
    ├── jaeger/                # jaeger-v2-config.yaml
    ├── loki/                  # loki-config.yaml
    ├── traefik/               # (configurazione via Docker labels in docker-compose.dev.yml)
    ├── otel-collector/        # otel-collector-config.yaml
    ├── postgres/              # init SQL (schema PostGIS)
    ├── prometheus/            # prometheus.yml + alert rules
    ├── promtail/              # promtail-config.yaml
    ├── redis/                 # redis.conf
    └── superset/              # superset_config.py + init script
```

## Note di configurazione

### Subdomain routing via Traefik

Ogni servizio è accessibile al proprio sottodominio `nomeservizio.${DOMAIN}` (es. `grafana.127.0.0.1.nip.io`).
Il routing è configurato tramite Docker labels direttamente in `docker-compose.dev.yml`.

| Servizio | Sottodominio | Auth |
|----------|--------------|------|
| Frontend | `frontend.${DOMAIN}` | No |
| Backoffice API | `backoffice.${DOMAIN}` | `/admin/` protetto |
| Grafana | `grafana.${DOMAIN}` | ForwardAuth |
| Jaeger | `jaeger.${DOMAIN}` | ForwardAuth |
| Prometheus | `prometheus.${DOMAIN}` | ForwardAuth |
| Superset | `superset.${DOMAIN}` | ForwardAuth |
| Airflow | `airflow.${DOMAIN}` | ForwardAuth |
| Flower | `flower.${DOMAIN}` | ForwardAuth |
| Loki | `loki.${DOMAIN}` | ForwardAuth |
| n8n | `n8n.${DOMAIN}` | ForwardAuth |
| Ollama | `ollama.${DOMAIN}` | ForwardAuth |
| oauth2-proxy | `auth.${DOMAIN}` | Pubblico |
| Traefik dashboard | `traefik.${DOMAIN}` | ForwardAuth |

`DOMAIN` si imposta in `infrastructures/.env` (default: `127.0.0.1.nip.io`).

### Rete Docker

Tutti i servizi sono collegati alla rete esterna `dev-network` (creata con `docker network create dev-network`).
Il compose Scrapyd (`microservices/scraping-service/docker-compose.yml`) usa la stessa rete.


OOM kill — il modello llama3.1:8B richiede ~4.7 GB di RAM solo per i pesi (CPU). Il processo viene terminato dal kernel per mancanza di memoria.
                                                                                                                                                                                                                                                           
  Soluzioni:                                                                                                                                                                                                                                               
                                         
  1. Usa un modello più piccolo (consigliato per dev su CPU):                                                                                                                                                                                              
  # qwen2.5:1.5b — ~1 GB RAM, veloce su CPU                
  make ollama-pull MODEL=qwen2.5:1.5b    

  # oppure llama3.2:1b — ~0.6 GB RAM
  make ollama-pull MODEL=llama3.2:1b

  Poi nell'interfaccia chat seleziona il modello piccolo dal menu in alto.

  2. Verifica quanta RAM ha Docker disponibile:
  docker info --format '{{.MemTotal}}' | awk '{printf "%.1f GB\n", $1/1073741824}'

  L8B è troppo pesante per girare in CPU dentro Docker su una macchina di sviluppo. Con qwen2.5:1.5b o llama3.2:1b funziona senza problemi.