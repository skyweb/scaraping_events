# Infrastructure - Today Events

Stack Docker per la gestione degli eventi:
- **PostgreSQL 16** con PostGIS 3.4
- **Redis 7**
- **Apache Airflow 2.8**
- **Scrapy Events** (container per spider)

## Quick Start

```bash
$ cd infrastructures

# 1. Build immagine Scrapy
$ docker-compose build scrapy-events

# 2. Avvia i servizi
$ docker compose up -d
$ docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
# 3. Verifica lo stato
$ docker-compose ps
```

## Servizi

| Servizio | Porta | Descrizione |
|----------|-------|-------------|
| PostgreSQL + PostGIS | 5432 | Database eventi |
| Redis | 6379 | Cache e message broker |
| Airflow Webserver | 8080 | UI Airflow |
| scrapy-events | - | Container per scraping |

  ┌────────────────────────────────────┬──────────┬──────────────────┐
  │              Servizio              │  Stato   │      Porta       │
  ├────────────────────────────────────┼──────────┼──────────────────┤
  │ Postgres (PostGIS)                 │ Healthy  │ 5432             │
  ├────────────────────────────────────┼──────────┼──────────────────┤
  │ Redis                              │ Healthy  │ 6379             │
  ├────────────────────────────────────┼──────────┼──────────────────┤
  │ Backoffice (Django dev server)     │ Starting │ 8000 (via Nginx) │
  ├────────────────────────────────────┼──────────┼──────────────────┤
  │ Backoffice Celery Worker           │ Starting │ -                │
  ├────────────────────────────────────┼──────────┼──────────────────┤
  │ Backoffice Celery Beat             │ Starting │ -                │
  ├────────────────────────────────────┼──────────┼──────────────────┤
  │ Nginx                              │ Up       │ 80               │
  ├────────────────────────────────────┼──────────┼──────────────────┤
  │ Airflow Webserver                  │ Starting │ 8080             │
  ├────────────────────────────────────┼──────────┼──────────────────┤
  │ Airflow Scheduler/Worker/Triggerer │ Starting │ -                │
  ├────────────────────────────────────┼──────────┼──────────────────┤
  │ Flower (Celery monitor)            │ Starting │ 5555             │
  ├────────────────────────────────────┼──────────┼──────────────────┤
  │ Redis UI (RedisInsight)            │ Up       │ 5540             │
  └────────────────────────────────────┴──────────┴──────────────────┘


## Container Scrapy

L'immagine `scrapy-events:latest` contiene tutti gli spider.

### Utilizzo manuale

```bash
# Build
$ docker-compose build scrapy-events

# Esegui city_today per Milano
$ docker run --rm -v $(pwd)/data:/data/output scrapy-events:latest \
    city_today milano --periodo=questa-settimana

# Esegui zero_eu per Roma e Bologna
$ docker run --rm -v $(pwd)/data:/data/output scrapy-events:latest \
    zero_eu roma bologna

# Mostra help
$ docker run --rm scrapy-events:latest city_today
```

### Comandi disponibili

```bash
# city_today
$ scrapy-events city_today <città> [--periodo=PERIODO]

# zero_eu
$ scrapy-events zero_eu <città>
```

**Periodi city_today**: oggi, domani, weekend, questa-settimana, prossima-settimana, questo-mese

## DAG Airflow

### scrape_events_daily
- **Schedule**: Ogni giorno alle 6:00
- **Pipeline**:
  1. `scrape_city_today` → Scraping tutte le città (questa-settimana)
  2. `scrape_zero_eu` → Scraping tutte le città
  3. `load_events_to_database` → Caricamento in PostgreSQL

### scrape_events_weekly
- **Schedule**: Ogni domenica alle 8:00
- **Task**: Scraping prossima settimana

### scrape_events_monthly
- **Schedule**: Primo del mese alle 4:00
- **Task**: Scraping questo mese

## Accesso

### PostgreSQL
```bash
psql -h localhost -U events -d today_events
# Password: events_secret_2026
```

### Redis
```bash
docker exec -it events-redis redis-cli -a redis_secret_2026
```

### Airflow
- URL: http://localhost:8080
- User: `admin`
- Password: `admin_secret_2026`

## Struttura Directory

```
infrastructures/
├── docker-compose.yml
├── .env
├── README.md
├── config/
│   ├── postgres/
│   │   └── init.sql
│   └── redis/
│       └── redis.conf
├── dags/
│   └── scrape_events_data.py
├── data/                    # Output JSON dagli spider
├── logs/
└── plugins/

scraping/
├── Dockerfile              # Immagine scrapy-events
├── entrypoint.sh
├── requirements.txt
├── city_today/
└── zero_eu/
```

## Database Schema

Il database `today_events` utilizza 3 schema PostgreSQL:

| Schema | Descrizione |
|--------|-------------|
| `events_data` | Eventi staging e production, viste |
| `comuni_istat` | Confini amministrativi ISTAT con geometrie PostGIS |
| `comuni_istat_ingestion` | Dati scraping comuni-italiani.it (modelli relazionali + raw JSON) |

### Schema `events_data`

```sql
SELECT uuid, title, city, date_start, source
FROM events_data.staging_events
ORDER BY date_start;
```

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| uuid | VARCHAR(16) | ID univoco (hash titolo+data+luogo) |
| content_hash | VARCHAR(16) | Hash contenuto (per detect modifiche) |
| source | VARCHAR(50) | 'city_today' o 'zero_eu' |
| city_id | INTEGER | FK a `comuni_istat.comuni(id)` |
| location_coords | GEOMETRY | Coordinate PostGIS |
| category | TEXT[] | Array categorie |
| raw_data | JSONB | JSON originale |

### Schema `comuni_istat`

Confini amministrativi ISTAT al 01/01/2025 con geometrie PostGIS:

| Tabella | Record | Descrizione |
|---------|--------|-------------|
| `ripartizioni` | 5 | Nord-Ovest, Nord-Est, Centro, Sud, Isole |
| `regioni` | 20 | Con geometrie MultiPolygon |
| `province` | 107 | Con sigla, geometrie |
| `comuni` | ~7900 | Con centroide, codice catastale, CAP, popolazione |

### Schema `comuni_istat_ingestion`

Dati arricchiti dallo scraping di comuni-italiani.it:

| Tabella | Descrizione |
|---------|-------------|
| `regioni` | 20 regioni con dati demografici |
| `province` | 110 province |
| `comuni` | ~8000 comuni con patrono, etimologia, demonimo |
| `comune_frazioni` | Frazioni e localita |
| `comune_confinanti` | Comuni limitrofi |
| `comune_appartenenze` | Comunita montane, parchi |
| `comune_punti_interesse` | Musei, chiese, castelli, teatri |
| `comune_eventi` | Feste, sagre tradizionali |
| `comune_gemellaggi` | Gemellaggi |
| `comune_cittadini_illustri` | Personaggi illustri |
| `raw_data` | JSON grezzi dallo scraping |

## Comandi Utili

```bash
# Avvia tutto
$ docker-compose up -d

# Build immagine scrapy
$ docker-compose build scrapy-events

# Stop tutto
$ docker-compose down

# Visualizza log
$ docker-compose logs -f airflow-scheduler

# Test scraping manuale
$ docker run --rm --network events-network \
    -v $(pwd)/data:/data/output \
    scrapy-events:latest city_today milano

# Query eventi
$ docker exec -it events-postgres psql -U events -d today_events \
    -c "SELECT COUNT(*), city FROM events_data.eventi GROUP BY city;"
```

## Configurazione Airflow Connection

Dopo l'avvio, crea la connection PostgreSQL in Airflow:

1. Vai su http://localhost:8080
2. Admin → Connections → Add
3. Configura:
   - Connection Id: `events_postgres`
   - Connection Type: `Postgres`
   - Host: `postgres`
   - Schema: `today_events`
   - Login: `events`
   - Password: `events_secret_2026`
   - Port: `5432`

  Funzioni SQL:
  - events_data.truncate_staging()
  - events_data.upsert_from_staging()
  - events_data.mark_missing_inactive()

  Accesso:
  - Airflow: http://localhost:8080 (admin / admin_secret_2026)
  - PostgreSQL: psql -h localhost -U events -d today_events

  Prossimo passo: Configura la connection PostgreSQL in Airflow:
  1. http://localhost:8080 → Admin → Connections → +
  2. Connection Id: events_postgres
  3. Type: Postgres
  4. Host: postgres, Port: 5432
  5. Schema: today_events
  6. Login: events, Password: events_secret_2026

## Bulk Ingestion Asincrono

L'endpoint `POST /api/external/staging/bulk/` supporta due modalita':

### Async (default)
```
POST /api/external/staging/bulk/
→ 202 Accepted + { task_id, status: "PENDING", message }
```
Il batch viene processato in background dal Celery worker. Per verificare lo stato:
```
GET /api/external/staging/bulk-status/{task_id}/
→ { task_id, status: "SUCCESS|PENDING|STARTED|FAILURE", result }
```

### Sync (backward compatible)
```
POST /api/external/staging/bulk/?sync=true
→ 201/200/400 + { created_count, failed_count, successful_events, failed_events }
```
Comportamento sincrono originale.

### Flusso Async

```
Scrapy ApiPipeline
    │ POST /api/external/staging/bulk/
    ▼
┌──────────────────────────┐
│ bulk() view              │
│ → valida payload         │
│ → process_bulk.delay()   │  ← dispatch a Celery
│ → return 202 + task_id   │  ← risposta immediata
└──────────────────────────┘
    │
    ▼ (Redis queue)
┌──────────────────────────┐
│ Celery Worker            │
│ process_bulk_events()    │
│ → validate each item     │
│ → bulk_create (batch DB) │  ← 1 query invece di N
│ → retry su errore DB     │
│ → salva risultato        │
└──────────────────────────┘
```

## Test API Staging Events

Test Django che leggono lo schema OpenAPI (drf-spectacular) ed eseguono
le richieste usando gli esempi JSON definiti nelle `@extend_schema`.

### Cosa testano

| Classe | Descrizione |
|--------|-------------|
| `OpenAPISchemaTest` | Validita' schema: paths, esempi, campi obbligatori |
| `StagingEventCreateFromSchemaTest` | POST `/api/external/staging/` con ogni esempio OpenAPI |
| `StagingEventBulkFromSchemaTest` | POST `/api/external/staging/bulk/` con esempi valid/partial/invalid |
| `StagingEventCRUDTest` | Ciclo completo: list, retrieve, create, update, patch, delete, filtri, search |
| `StagingEventClearSourceTest` | DELETE `/api/external/staging/clear_source/?source=xxx` |
| `StagingEventAuthTest` | OAuth2: token assente, scaduto, invalido, scope read vs write |

### Come lanciare

```bash
# Output tabellare (endpoint, metodo, status, esito)
docker exec -w /app/backend events-backoffice \
  python manage.py test events.tests.test_staging_api \
  --testrunner events.tests.runner.TableTestRunner

# Output standard Django (-v2 per dettaglio)
docker exec -w /app/backend events-backoffice \
  python manage.py test events.tests.test_staging_api -v2

# Solo una classe specifica
docker exec -w /app/backend events-backoffice \
  python manage.py test events.tests.test_staging_api.StagingEventBulkFromSchemaTest -v2

# Solo un singolo test
docker exec -w /app/backend events-backoffice \
  python manage.py test events.tests.test_staging_api.StagingEventCRUDTest.test_create_event -v2
```

### Esempio output tabellare

```
Metodo | Endpoint                            | Status | Esito | Test
-------+-------------------------------------+--------+-------+------------------------------------------
GET    | /api/external/staging/              | 200    | PASS  | test_list_events
POST   | /api/external/staging/              | 201    | PASS  | test_create_with_each_schema_example
POST   | /api/external/staging/bulk/         | 201    | PASS  | test_bulk_create_all_valid
DELETE | /api/external/staging/clear_source/ | 200    | PASS  | test_clear_source_deletes_matching
GET    | /api/external/staging/              | 401    | PASS  | test_no_token_returns_401
...
Totale: 36  |  Pass: 36
```

### Note

- I test creano un database temporaneo (`test_today_events`) e lo distruggono a fine esecuzione
- Le migrazioni RunSQL creano automaticamente lo schema `events_data` nel DB di test
- L'autenticazione OAuth2 viene simulata con token creati in `setUpTestData`
- Gli esempi JSON vengono estratti dallo schema generato da `SchemaGenerator` di drf-spectacular
