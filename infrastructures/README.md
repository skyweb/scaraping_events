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
$ docker-compose up -d

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

websites/
├── Dockerfile              # Immagine scrapy-events
├── entrypoint.sh
├── requirements.txt
├── city_today/
└── zero_eu/
```

## Database Schema

```sql
-- Schema: events
-- Tabella: events_data.eventi

SELECT uuid, title, city, date_start, source
FROM events_data.eventi
ORDER BY date_start;
```

### Campi principali

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| uuid | VARCHAR(16) | ID univoco (hash titolo+data+luogo) |
| content_hash | VARCHAR(16) | Hash contenuto (per detect modifiche) |
| source | VARCHAR(50) | 'city_today' o 'zero_eu' |
| location_coords | GEOMETRY | Coordinate PostGIS |
| category | TEXT[] | Array categorie |
| raw_data | JSONB | JSON originale |

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
                                      