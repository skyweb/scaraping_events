# Events Test Suite

Suite test organizzata per dominio e tipologia, con focus su:

- bulk ingestion eventi
- operazioni CRUD e lifecycle eventi
- API interne backoffice
- API pubbliche/versionate
- regressioni, performance e sicurezza

## Struttura

```text
events/tests/
├── api/
│   ├── internal/
│   └── public/
├── database/
├── fixtures/
├── models/
├── performance/
├── regression/
├── security/
├── unit/
├── factories.py
├── helpers.py
└── runner.py
```

## Regole organizzative

- `unit/`: serializer, normalizzazione payload, logica locale senza focus sul trasporto HTTP
- `models/`: comportamento del modello `Event`
- `database/`: task bulk, query rilevanti, comportamento DB-oriented
- `api/internal/`: endpoint backoffice sotto `/api/`
- `api/public/`: endpoint esterni/versionati sotto `/api/v1/events/`
- `regression/`: bug già emersi e corretti
- `performance/`: query count e scenari mirati
- `security/`: auth, permessi, data exposure

## Helper condivisi

- `helpers.py`: payload esempio e base test case per API interne/esterne
- `factories.py`: factory leggere per `Event`, `ApiConsumer` e utente staff

L'obiettivo è evitare:

- setup duplicato
- payload hardcoded copiati in più file
- test monolitici da centinaia di righe

## Comandi di esecuzione

Eseguire dalla root backend:

```bash
cd microservices/backoffice-service/backend
```

Suite completa `events`:

```bash
python manage.py test events.tests
```

Solo unit:

```bash
python manage.py test events.tests.unit
```

Solo model:

```bash
python manage.py test events.tests.models
```

Solo database/bulk task:

```bash
python manage.py test events.tests.database
```

Solo API interne:

```bash
python manage.py test events.tests.api.internal
```

Solo API pubbliche:

```bash
python manage.py test events.tests.api.public
```

Solo security:

```bash
python manage.py test events.tests.security
```

Solo regression:

```bash
python manage.py test events.tests.regression
```

Solo performance:

```bash
python manage.py test events.tests.performance
```

Runner tabellare per API:

```bash
python manage.py test events.tests.api.public --testrunner events.tests.runner.TableTestRunner
```

Oppure dalla root `microservices/backoffice-service` via `Makefile`:

```bash
make test-events
make test-events-unit
make test-events-models
make test-events-db
make test-events-api-internal
make test-events-api-public
make test-events-security
make test-events-regression
make test-events-performance
make test-events-api-table
```

Coverage della suite `events`:

```bash
make coverage-events
make coverage-events-report
make coverage-events-html
```

Report HTML generato in:

[`backend/htmlcov/index.html`](/Users/skyweb/Sites/dev/scaraping_events/microservices/backoffice-service/backend/htmlcov/index.html)

## Prerequisiti ambiente

Questa suite usa Django reale e il database configurato in `backoffice.settings`.

Servono almeno:

- `POSTGRES_PASSWORD`
- accesso al database configurato
- dipendenze Django installate

Se l'ambiente locale non espone `POSTGRES_PASSWORD`, la discovery Django fallisce prima di eseguire i test.

Se hai appena aggiunto `coverage` alle dipendenze dev del container, ricordati di rebuildare l'immagine:

```bash
make dev-build
make dev-up
```

## Naming convention

- file: `test_<feature>.py`
- classi: `<Feature>Test`
- test methods: `test_<behavior>_<expected_result>`

Preferire file piccoli e mirati. Quando un file supera molto una singola responsabilità, va spezzato.

## Coverage Matrix

### Bulk ingestion

- validazione payload scraping: `unit/test_event_scraping_serializer.py`
- validazione payload legacy: `unit/test_event_legacy_serializer.py`
- processing task bulk: `database/test_bulk_task.py`
- bulk sync/async endpoint: `api/public/test_bulk_ingestion.py`
- regressioni upsert e nested spider format: `regression/test_bulk_ingestion_regressions.py`
- query count del task: `performance/test_bulk_ingestion_performance.py`

### Event lifecycle

- create/list/retrieve/delete pubblico: `api/public/test_event_crud.py`
- ranking e rappresentazione model: `models/test_event_model.py`
- dashboard e toggle interno: `api/internal/test_production_event_api.py`

### Security

- richiesta senza auth: `security/test_external_event_permissions.py`
- consumer read-only: `security/test_external_event_permissions.py`
- consumer scaduto: `security/test_external_event_permissions.py`
- riduzione campi piano free: `security/test_external_event_permissions.py`

## Gap attuali da coprire dopo

- test dedicati per `clear_source`
- test dedicati per filtri/ordering/search sulle API pubbliche
- test dedicati per `bulk_status` failure/pending multipli
- test DB su unique/constraint e comportamento transazionale avanzato
- test performance su list endpoint e query count serializer
