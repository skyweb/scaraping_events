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

### API Endpoints

**API Interne** (prefisso `/api/`):

| Endpoint | Descrizione |
|---|---|
| `/api/events/` | CRUD Production Events |
| `/api/events/{id}/toggle_active/` | Toggle attivo/inattivo evento |
| `/api/events/cities/` | Lista citta con conteggio eventi |
| `/api/events/sources/` | Lista sorgenti con conteggio eventi |
| `/api/staging/` | Lista Staging Events (read-only) |
| `/api/etl-runs/` | Storico esecuzioni ETL |
| `/api/etl-errors/` | Storico errori ETL |
| `/api/dashboard/` | Statistiche aggregate |

**API Esterne - OAuth2** (prefisso `/api/external/`):

| Endpoint | Metodi | Scope | Descrizione |
|---|---|---|---|
| `/api/external/staging/` | GET, POST, PUT, PATCH, DELETE | read/write | CRUD Staging Events |
| `/api/external/staging/bulk/` | POST | write | Creazione massiva eventi |
| `/api/external/staging/clear_source/?source=xxx` | DELETE | write | Elimina eventi per sorgente |

### Autenticazione API Esterne

Le API esterne richiedono un token OAuth2 (Client Credentials):

```bash
# 1. Ottieni access token
curl -X POST http://localhost:8000/oauth/token/ \
  -d "grant_type=client_credentials" \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET"

# 2. Usa il token nelle richieste
curl -H "Authorization: Bearer ACCESS_TOKEN" \
  http://localhost:8000/api/external/staging/
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
docker exec -it backoffice-backend-dev python manage.py createsuperuser
```

Segui le istruzioni a schermo per impostare username, email e password.

## Comandi Utili

### Database Migrations

Applicare le migrazioni:
```bash
docker exec -it backoffice-backend-dev python manage.py migrate
```

Creare nuove migrazioni (dopo aver modificato i modelli):
```bash
docker exec -it backoffice-backend-dev python manage.py makemigrations
```

### Logs

Vedere i log del backend:
```bash
docker logs -f backoffice-backend-dev
```

Vedere i log del frontend:
```bash
docker logs -f backoffice-frontend-dev
```

## Django Apps

| App | Descrizione |
|-----|-------------|
| `events` | Gestione eventi (Staging + Production), ETL, API esterne OAuth2 |
| `scraping` | Configurazione spider e categorie |
| `cms` | CMS pagine citta: sezioni, articoli, staging events integrati |
| `comuni_istat` | Confini amministrativi ISTAT (regioni, province, comuni con geometrie PostGIS) |
| `comuni_istat_ingestion` | Dati scraping comuni-italiani.it: modelli relazionali + raw data JSON |
| `etl` | Storico esecuzioni e errori ETL |

### App `comuni_istat_ingestion`

Contiene i modelli relazionali per i dati scraping da comuni-italiani.it:

| Modello | Tabella DB | Descrizione |
|---------|-----------|-------------|
| `Regione` | `regioni` | 20 regioni con dati demografici |
| `Provincia` | `province` | 110 province con sigla, popolazione, superficie |
| `Comune` | `comuni` | ~8000 comuni con CAP, patrono, etimologia, ecc. |
| `ComuneFrazione` | `comune_frazioni` | Frazioni e localita |
| `ComuneConfinante` | `comune_confinanti` | Comuni confinanti |
| `ComuneAppartenenza` | `comune_appartenenze` | Comunita montane, parchi, associazioni |
| `ComunePuntoInteresse` | `comune_punti_interesse` | Musei, chiese, castelli, teatri, stadi |
| `ComuneEvento` | `comune_eventi` | Feste, sagre, eventi tradizionali |
| `ComuneGemellaggio` | `comune_gemellaggi` | Gemellaggi con altre citta |
| `ComuneCittadinoIllustre` | `comune_cittadini_illustri` | Cittadini illustri |
| `ComuniIstatRawData` | `raw_data` | Dati JSON grezzi dallo scraping |

Tutte le tabelle sono nello schema PostgreSQL `comuni_istat_ingestion`.

#### Management Command: `import_scraping_comuni`

Importa i JSON generati dallo spider `comuni_spider` nelle tabelle relazionali:

```bash
# Copia i JSON nel container
docker cp /path/to/scraping-comuni-service/data/output dev-backoffice:/tmp/scraping_output

# Importa (--flush cancella i dati esistenti prima)
docker exec dev-backoffice python manage.py import_scraping_comuni /tmp/scraping_output --flush
```

### API Endpoints Comuni

| Endpoint | Metodi | Descrizione |
|----------|--------|-------------|
| `/api/comuni-istat/ingestion/` | POST | Ingestione singolo record |
| `/api/comuni-istat/ingestion/bulk/` | POST | Ingestione bulk |

### CMS

| Endpoint | Metodi | Descrizione |
|----------|--------|-------------|
| `/api/cms/citta/` | GET | Lista pagine citta attive |
| `/api/cms/citta/{slug}/` | GET | Dettaglio pagina citta con sezioni e articoli |

## Struttura

- **backend/**: Applicazione Django (API + Admin)
- **frontend/**: Applicazione React/Vite (UI personalizzata)
- **docker-compose.dev.yml**: Configurazione Docker per l'ambiente di sviluppo
