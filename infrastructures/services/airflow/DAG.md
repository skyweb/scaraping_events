# Airflow DAG - Guida operativa

Container di riferimento: `dev-airflow-webserver`

## DAG disponibili

| DAG ID | Descrizione | Schedule | Tags |
|--------|-------------|----------|------|
| `etl_events_daily` | ETL giornaliero eventi (questa settimana) | `0 6 * * *` (ogni giorno alle 06:00) | events, etl, daily |
| `etl_events_weekly` | ETL settimanale eventi (prossima settimana) | `0 8 * * 0` (domenica alle 08:00) | events, etl, weekly |
| `etl_events_monthly` | ETL mensile eventi (questo mese) | `0 4 1 * *` (1° del mese alle 04:00) | events, etl, monthly |
| `etl_comuni_istat` | ETL comuni ISTAT (scraping + ingestion) | Manuale (one-shot) | comuni, etl, one-shot |

---

## etl_events_daily / weekly / monthly

### Task

Ogni DAG eventi ha la stessa struttura:
- **TaskGroup `process_{citta}`** — un gruppo per ogni citta con sotto-task:
  - `scrape_city_today` — spider city_today
  - `scrape_zero_eu` — spider zero_eu (solo daily)
  - `scrape_{spider}` — spider turismo (se configurato)
- **TaskGroup `regionali`** — sotto-gruppi per regione con spider regionali
- **`log_etl_run`** — log del run ETL (eseguito alla fine)

### Trigger DAG completo

```bash
# DAG giornaliero
docker exec dev-airflow-webserver airflow dags trigger etl_events_daily

# DAG settimanale
docker exec dev-airflow-webserver airflow dags trigger etl_events_weekly

# DAG mensile
docker exec dev-airflow-webserver airflow dags trigger etl_events_monthly
```

### Filtro per citta

```bash
# Solo Milano
docker exec dev-airflow-webserver airflow dags trigger etl_events_daily \
  --conf '{"city": "milano"}'

# Solo Milano e Roma
docker exec dev-airflow-webserver airflow dags trigger etl_events_daily \
  --conf '{"cities_today": "milano,roma"}'

# Solo zero_eu per Milano
docker exec dev-airflow-webserver airflow dags trigger etl_events_daily \
  --conf '{"cities_zero": "milano"}'

# Solo city_today per Milano (escludi zero_eu)
docker exec dev-airflow-webserver airflow dags trigger etl_events_daily \
  --conf '{"city": "milano", "cities_today": []}'
```

### Esegui singolo task

```bash
# Test (non salva nel DB, utile per debug)
docker exec dev-airflow-webserver airflow tasks test etl_events_daily \
  process_milano.scrape_city_today 2026-03-21

docker exec dev-airflow-webserver airflow tasks test etl_events_daily \
  process_milano.scrape_zero_eu 2026-03-21

# Run (salva nel DB)
docker exec dev-airflow-webserver airflow tasks run etl_events_daily \
  process_milano.scrape_zero_eu 2026-03-21

# Log ETL
docker exec dev-airflow-webserver airflow tasks test etl_events_daily \
  log_etl_run 2026-03-21
```

---

## etl_comuni_istat

### Task (sequenziali)

```
scrape_comuni → ingest_regioni → ingest_province → ingest_comuni
```

1. **`scrape_comuni`** — DockerOperator, lancia lo spider Scrapy per comuni-italiani.it
2. **`ingest_regioni`** — PythonOperator, importa regioni dal JSON/MinIO
3. **`ingest_province`** — PythonOperator, importa province
4. **`ingest_comuni`** — PythonOperator, importa comuni + tabelle figlie

### Trigger DAG completo

```bash
docker exec dev-airflow-webserver airflow dags trigger etl_comuni_istat
```

### Esegui singolo task

```bash
# Test singolo task (non salva nel DB)
docker exec dev-airflow-webserver airflow tasks test etl_comuni_istat \
  ingest_regioni 2026-03-21

docker exec dev-airflow-webserver airflow tasks test etl_comuni_istat \
  ingest_province 2026-03-21

docker exec dev-airflow-webserver airflow tasks test etl_comuni_istat \
  ingest_comuni 2026-03-21

# Run (salva nel DB)
docker exec dev-airflow-webserver airflow tasks run etl_comuni_istat \
  ingest_regioni 2026-03-21
```

---

## Configurazione API Variables

Il DAG eventi usa le **Airflow Variables** per le credenziali API (con fallback sulle variabili d'ambiente).

### Da UI

1. Accedi a Airflow: `https://airflow.127.0.0.1.nip.io`
2. Vai su `Admin` → `Variables`
3. Aggiungi:

| Key | Valore | Descrizione |
|-----|--------|-------------|
| `API_BASE_URL` | `http://backoffice:8000` | URL interno backoffice (rete Docker) |
| `API_CLIENT_ID` | `scraper-service` | Username API consumer (da Django admin API Consumers) |
| `API_CLIENT_SECRET` | `<secret da Django admin>` | API key del consumer |
| `KEYCLOAK_TOKEN_URL` | `http://keycloak:8080/realms/today-events/protocol/openid-connect/token` | Token endpoint Keycloak (rete Docker) |

### Da CLI

```bash
docker exec dev-airflow-webserver airflow variables set API_BASE_URL "http://backoffice:8000"
docker exec dev-airflow-webserver airflow variables set API_CLIENT_ID "scraper-service"
docker exec dev-airflow-webserver airflow variables set API_CLIENT_SECRET "<secret da Django admin API Consumers>"
docker exec dev-airflow-webserver airflow variables set KEYCLOAK_TOKEN_URL "http://keycloak:8080/realms/today-events/protocol/openid-connect/token"

# Verifica
docker exec dev-airflow-webserver airflow variables list
```

### Creare/rigenerare le credenziali

Le credenziali si gestiscono dal Django admin:

1. Vai su `https://backoffice.127.0.0.1.nip.io/admin/api_consumers/apiconsumer/`
2. Crea o modifica il consumer `scraper-service`
3. Copia l'API key generata in `API_CLIENT_SECRET`

### Fallback

Se le Variables non sono configurate, il DAG usa le variabili d'ambiente dal `.env`:
- `API_BASE_URL` → default: vuoto
- `API_CLIENT_ID` → default: vuoto
- `API_CLIENT_SECRET` → default: vuoto

---

## Comandi utili

```bash
# Lista DAG
docker exec dev-airflow-webserver airflow dags list

# Stato di un DAG
docker exec dev-airflow-webserver airflow dags state etl_events_daily

# Lista task di un DAG
docker exec dev-airflow-webserver airflow tasks list etl_events_daily --tree

# Pausa / riattiva DAG
docker exec dev-airflow-webserver airflow dags pause etl_events_daily
docker exec dev-airflow-webserver airflow dags unpause etl_events_daily

# Log del DAG processor
tail -f infrastructures/services/airflow/logs/dag_processor_manager/dag_processor_manager.log
```
