# Microservizi - Today Events

Panoramica dei microservizi che compongono la piattaforma Today Events.

---

## Architettura generale

```
┌─────────────────────────────────────────────────────────────────┐
│                      INFRASTRUCTURE                             │
│   PostgreSQL + PostGIS · Redis · Nginx · Airflow               │
│   OpenTelemetry · Prometheus · Grafana · Loki · Jaeger         │
└─────────────────────────────────────────────────────────────────┘
         ↑                   ↑                    ↑
┌─────────────────┐  ┌────────────────┐  ┌─────────────────────┐
│backoffice-      │  │scraping-       │  │scraping-comuni-     │
│service          │  │service         │  │service              │
│Django + DRF     │  │Scrapy+Scrapyd  │  │Scrapy (batch)       │
│Port: 8000       │  │Port: 6800      │  │(no porta esposta)   │
└─────────────────┘  └────────────────┘  └─────────────────────┘
         ↑                   │ OAuth2 POST /api/v1/events/staging/bulk/
         └───────────────────┘
         ↑
┌─────────────────┐
│frontend-service │
│React + Vite     │
│Port: 5173 (dev) │
│Port: 80 (prod)  │
└─────────────────┘
```

---

## 1. backoffice-service

**Ruolo:** Backend centrale della piattaforma. Gestisce eventi, amministrazione, API e task asincroni.

**Stack:**
- Django 5.0 + Django REST Framework
- Unfold Admin (UI amministrativa avanzata)
- Celery + Celery Beat (task asincroni e schedulati)
- PostgreSQL 16 + PostGIS (dati spaziali)
- Redis (broker Celery, cache, sessioni)
- OAuth2 (django-oauth-toolkit) per autenticazione scraper
- OpenTelemetry + Prometheus (osservabilità)
- drf-spectacular (documentazione OpenAPI 3.0)

**Porte:** `8000`

**Django Apps principali:**
| App | Descrizione |
|-----|-------------|
| `events` | Gestione eventi Staging e Production, pipeline ETL |
| `scraping` | Configurazione spider e categorie di scraping |
| `cms` | CMS pagine città (sezioni, articoli, staging events) |
| `comuni_istat` | Confini amministrativi ISTAT (regioni, province, comuni + PostGIS) |
| `comuni_italiani` | Dati relazionali da scraping comuni-italiani.it |
| `etl` | Storico esecuzioni ETL ed errori |

**API principali:**
| Endpoint | Descrizione |
|----------|-------------|
| `POST /api/v1/events/staging/bulk/` | Ricezione eventi da scraper (OAuth2) |
| `GET /api/events/` | CRUD eventi in produzione |
| `GET /api/staging/` | Visualizzazione eventi in staging |
| `GET /api/cms/citta/{slug}/` | Pagine città con sezioni e articoli |
| `POST /api/comuni-istat/ingestion/bulk/` | Ingestione dati comuni |
| `GET /api/dashboard/` | Statistiche aggregate |
| `/api/docs/` | Swagger UI |

**Dipende da:** PostgreSQL, Redis
**Riceve dati da:** scraping-service, scraping-comuni-service
**Serve:** frontend-service

---

## 2. frontend-service

**Ruolo:** Interfaccia web SPA per il backoffice operativo.

**Stack:**
- React 19 + TypeScript 5.9
- Vite 7.3 (build tool, HMR in dev)
- Tailwind CSS 4.1 + Radix UI (headless components)
- Lucide React (icone)
- Nginx (server statico in produzione)

**Porte:**
- `5173` in sviluppo (Vite dev server)
- `80` in produzione (Nginx)

**Funzionalità:**
- Visualizzazione e gestione eventi staging/production
- Dashboard con statistiche
- CMS sezioni città
- Comunicazione REST con `backoffice-service`

**Dipende da:** backoffice-service (`/api/*`)

---

## 3. scraping-service

**Ruolo:** Scraping distribuito di eventi da fonti italiane. Espone un server HTTP (Scrapyd) per la gestione remota degli spider.

**Stack:**
- Scrapy 2.11 + Scrapyd 1.4
- PostgreSQL + psycopg2 (salvataggio opzionale)
- OpenTelemetry (distributed tracing)

**Porte:** `6800` (Scrapyd HTTP API)

**Spider disponibili:**
| Spider | Sorgente | Contenuto |
|--------|----------|-----------|
| `zero_eu` | zero.eu | Concerti, mostre, teatro |
| `city_today` | rete Today.it (50+ città) | Tutti i tipi di eventi urbani |
| `artribune` | artribune.com | Mostre ed eventi culturali |

**Pipeline di elaborazione:**
1. `ValidationPipeline` — Validazione struttura item
2. `HashGeneratorPipeline` — Generazione UUID univoco per deduplicazione
3. `PostgresPipeline` — Salvataggio su DB (opzionale)
4. `APIBackofficePostPipeline` — Push verso backoffice via `POST /api/v1/events/staging/bulk/` (OAuth2 Client Credentials)

**Dipende da:** backoffice-service (push OAuth2), PostgreSQL (opzionale)
**Orchestrato da:** Airflow (via Scrapyd HTTP API)

---

## 4. scraping-comuni-service

**Ruolo:** Scraping batch dei dati sui comuni italiani da comuni-italiani.it. Genera file JSON strutturati per l'ingestione nel backoffice.

**Stack:**
- Scrapy 2.11
- Docker (esecuzione one-shot, nessun server persistente)

**Porte:** Nessuna (esecuzione batch)

**Spider:** `comuni_spider`

**Dati estratti per ogni comune:**
| Entità | Descrizione |
|--------|-------------|
| Regione / Provincia / Comune | Dati anagrafici e demografici |
| Frazioni | Locality e frazioni del comune |
| Confinanti | Comuni confinanti |
| Appartenenze | Comunità montane, parchi, associazioni |
| Punti di interesse | Musei, chiese, castelli, stadi, teatri |
| Eventi | Feste, sagre, eventi tradizionali |
| Gemellaggi | Gemellaggi internazionali |
| Cittadini illustri | Personaggi storici e contemporanei |

**Output:** File JSON in `data/output/`

**Ingestione nel backoffice:**
```bash
# Eseguire nel container backoffice-service
python manage.py import_scraping_comuni /path/to/output [--flush]
```

**Dipende da:** backoffice-service (management command per ingestione)

---

## Stack condiviso (infrastructure)

I seguenti servizi sono definiti in `infrastructures/` e condivisi tramite la rete Docker `dev-network`:

| Servizio | Tecnologia | Scopo |
|----------|------------|-------|
| Database | PostgreSQL 16 + PostGIS | Storage principale |
| Cache/Broker | Redis 7 | Celery broker, cache Django |
| Proxy | Nginx | Reverse proxy, TLS termination |
| Orchestrazione | Apache Airflow 2.8 | Scheduling spider e pipeline |
| Tracing | Jaeger + OpenTelemetry | Distributed tracing |
| Metriche | Prometheus + Grafana | Monitoraggio |
| Log | Loki | Aggregazione log |
