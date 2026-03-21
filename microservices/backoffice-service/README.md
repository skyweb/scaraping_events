# Service Backoffice - Today Events

Questo servizio gestisce il pannello di amministrazione per Today Events, composto da un backend Django e un frontend React/Vite.

## Prerequisiti

Assicurati che l'infrastruttura principale (PostgreSQL) sia in esecuzione:

```bash
$ cd infrastructures
$ docker-compose up -d
```

## Quick Start (Sviluppo)

1. Spostati nella directory del servizio:
   ```bash
   $ cd services/service-backoffice
   ```

2. Avvia i container di sviluppo:
   ```bash
   $  docker compose -f docker-compose.dev.yml up -d
   ```

3. Verifica che i servizi siano attivi:
   ```bash
   $ docker compose -f docker-compose.dev.yml ps
   ```

4. lancio manuale
   ```bash
   $ export DJANGO_DEBUG=True
   $ export POSTGRES_HOST=localhost
   ```

## Accesso ai Servizi

- **Frontend (Backoffice UI):** [http://localhost:3000](http://localhost:3000)
- **Backend API:** [http://localhost:8000](http://localhost:8000)
- **Django Admin:** [http://localhost:8000/admin](http://localhost:8000/admin)

## API Documentation

La documentazione delle API viene generata automaticamente tramite **drf-spectacular** (OpenAPI 3.0).

### Rotte documentazione

| URL | Descrizione |
|---|---|
| `/api/docs/` | Swagger UI interattivo (API interne) |
| `/api/schema/` | Schema OpenAPI raw (JSON/YAML) |
| `/docs/` | Swagger UI pubblico (API esterne) |
| `/docs/redoc/` | ReDoc - documentazione alternativa |
| `/docs/schema/` | Schema OpenAPI pubblico (JSON/YAML) |

Per scaricare lo schema in formato specifico:
```
GET /api/schema/?format=yaml
GET /api/schema/?format=json
```
### Autenticazione API Esterne

Le API esterne richiedono un token OAuth2 (Client Credentials):

```bash
# 1. Ottieni access token
curl -X POST http://localhost:8000/oauth/token/ \
  -d "grant_type=client_credentials" \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET"
```

### Celery (Task asincroni)

Il backoffice utilizza Celery con Redis come broker per task asincroni e scheduling periodico.

| Servizio | Descrizione |
|---|---|
| `backoffice-celery-worker` | Worker per esecuzione task |
| `backoffice-celery-beat` | Scheduler per task periodici |

I task periodici sono configurabili da Django Admin nella sezione **Celery** > **Periodic Tasks**.

## Gestione Utenti (Django)

### Creare un Superuser

Per accedere all'interfaccia di amministrazione di Django o al Backoffice come amministratore, devi creare un superuser. Esegui questo comando mentre i container sono attivi:

```bash
docker exec -it dev-backoffice python manage.py createsuperuser
```

Segui le istruzioni a schermo per impostare username, email e password.

## Comandi Utili

### Database Migrations

Applicare le migrazioni:
```bash
docker exec -it dev-backoffice python manage.py migrate
```

Creare nuove migrazioni (dopo aver modificato i modelli):
```bash
docker exec -it dev-backoffice python manage.py makemigrations
```

### Logs

Vedere i log del backend:
```bash
docker logs -f dev-backoffice
```

Vedere i log del frontend:
```bash
docker logs -f backoffice-frontend-dev
```
#### Management Command: `import_scraping_comuni`

Importa i JSON generati dallo spider `comuni_spider` nelle tabelle relazionali.

**Via Makefile (consigliato):**

```bash
cd microservices/backoffice-service

# Importazione (legge automaticamente da ../scraping-comuni-service/data/output)
make dev-import-comuni

# Con flush dei dati esistenti prima dell'import
make dev-import-comuni FLUSH=--flush
```

**Manualmente via Docker:**

```bash
# 1. Copia i JSON nel container
docker cp microservices/scraping-comuni-service/data/output dev-backoffice:/tmp/scraping_output

# 2. Importa
docker exec dev-backoffice python manage.py import_scraping_comuni /tmp/scraping_output

# 2b. Oppure con flush (cancella dati esistenti prima)
docker exec dev-backoffice python manage.py import_scraping_comuni /tmp/scraping_output --flush

# 3. Pulizia file temporanei
docker exec dev-backoffice rm -rf /tmp/scraping_output
```

## Bulk Ingestion Asincrono

L'endpoint `POST /api/v1/events/staging/bulk/` supporta due modalita':

### Async (default)
```
POST /api/v1/events/staging/bulk/
→ 202 Accepted + { task_id, status: "PENDING", message }
```
Il batch viene processato in background dal Celery worker. Per verificare lo stato:
```
GET /api/v1/events/staging/bulk-status/{task_id}/
→ { task_id, status: "SUCCESS|PENDING|STARTED|FAILURE", result }
```

### Sync (backward compatible)
```
POST /api/v1/events/staging/bulk/?sync=true
→ 201/200/400 + { created_count, failed_count, successful_events, failed_events }
```
Comportamento sincrono originale.

### Flusso Async

```
Scrapy ApiPipeline
    │ POST /api/v1/events/staging/bulk/
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
