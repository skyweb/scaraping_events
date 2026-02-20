# Events Scraper

Progetto Scrapy per lo scraping di eventi da diverse fonti italiane

## Spider Disponibili

| Spider | Fonte | Descrizione |
|--------|-------|-------------|
| `zero_eu` | [zero.eu](https://zero.eu) | Eventi culturali (concerti, mostre, teatro) |
| `city_today` | Rete *Today.it | 50+ città italiane (MilanoToday, RomaToday, etc.) |
| `artribune` | [artribune.com](https://artribune.com) | Mostre d'arte e eventi culturali |
| `in_lombardia` | [in-lombardia.it](https://www.in-lombardia.it) | Portale eventi della Lombardia (JSON-LD Schema.org) |
| `la_mia_liguria` | [lamialiguria.it](https://lamialiguria.it) | Portale turistico eventi della Liguria (WordPress) |

## Quick Start

### Con Docker

```bash
# Build dell'immagine
docker compose build

# Avvia Scrapyd server
docker compose up -d

# Verifica che sia attivo
curl http://localhost:6800/daemonstatus.json
```

### Senza Docker (Locale)

```bash
# Entra nella cartella del servizio
cd services/service-scraping

# Crea e attiva venv (se non esiste)
python -m venv venv
source venv/bin/activate

# Installa dipendenze
pip install -r src/requirements.txt

# Esegui spider (dalla cartella src)
cd src
scrapy crawl city_today -a cities=milano -o milano.json
```

## Utilizzo con Scrapyd

Scrapyd è un server HTTP per la gestione degli spider Scrapy. Permette di schedulare, monitorare e gestire gli spider tramite API REST.

### Dashboard

Dopo l'avvio, la dashboard è disponibile su: http://localhost:6800

### API Endpoints

#### Schedulare uno Spider

```bash
# Spider city_today - singola città
curl http://localhost:6800/schedule.json \
  -d project=events_scraper \
  -d spider=city_today \
  -d cities=milano

# Spider city_today - multiple città
curl http://localhost:6800/schedule.json \
  -d project=events_scraper \
  -d spider=city_today \
  -d cities=milano,roma,bologna \
  -d periodo=weekend

# Spider zero_eu
curl http://localhost:6800/schedule.json \
  -d project=events_scraper \
  -d spider=zero_eu \
  -d city=roma

# Spider artribune
curl http://localhost:6800/schedule.json \
  -d project=events_scraper \
  -d spider=artribune \
  -d max_pages=5
```

#### Monitorare Job

```bash
# Lista job attivi
curl http://localhost:6800/listjobs.json?project=events_scraper

# Stato daemon
curl http://localhost:6800/daemonstatus.json
```

#### Cancellare Job

```bash
curl http://localhost:6800/cancel.json \
  -d project=events_scraper \
  -d job=JOB_ID
```

## Parametri Spider

### city_today

| Parametro | Descrizione | Default |
|-----------|-------------|---------|
| `cities` | Lista città separate da virgola | Tutte |
| `periodo` | Filtro temporale | `questa-settimana` |

**Città supportate:** milano, roma, torino, bologna, firenze, napoli, venezia, genova, palermo, bari, catania, verona, padova, trieste, brescia, parma, modena, reggio-emilia, piacenza, rimini, ravenna, forli, cesena, ancona, pescara, perugia, arezzo, livorno, pisa, latina, frosinone, viterbo, terni, lecce, brindisi, foggia, salerno, avellino, caserta, messina, agrigento, reggio-calabria, como, monza, lecco, sondrio, novara, treviso, trento, udine, pordenone, vicenza

**Periodi:** `oggi`, `domani`, `weekend`, `questa-settimana`, `prossima-settimana`, `questo-mese`

### zero_eu

| Parametro | Descrizione | Default |
|-----------|-------------|---------|
| `city` | Slug città | `milano` |

**Città:** milano, roma, bologna, torino, firenze, venezia, napoli

### artribune

| Parametro | Descrizione | Default |
|-----------|-------------|---------|
| `max_pages` | Limite pagine | Tutte |
| `per_page` | Eventi per pagina | 100 |

### in_lombardia

| Parametro | Descrizione | Default |
|-----------|-------------|---------|
| `max_pages` | Numero massimo pagine listing | `5` |

Usa JSON-LD Schema.org `@type: Event` per titolo, date, location, immagine.
Integra categoria (tassonomia Drupal), prezzo e orario dall'HTML.

### la_mia_liguria

| Parametro | Descrizione | Default |
|-----------|-------------|---------|
| `max_pages` | Numero massimo pagine listing | `5` |

Sito WordPress con JSON-LD `WebPage`. Date da `.data-inizio`/`.data-fine`,
città da `.event-location`, categoria dalla card listing.

## Output

Gli eventi vengono estratti con la seguente struttura:

```json
{
  "source": "city_today",
  "url": "https://www.milanotoday.it/eventi/...",
  "uuid": "a1b2c3d4e5f6g7h8",
  "title": "Nome Evento",
  "description": "Descrizione completa...",
  "category": ["Musica", "Concerti"],
  "image_url": "https://...",
  "city": "Milano",
  "location_name": "Teatro XYZ",
  "location_address": "Via Roma 123, Milano",
  "date_start": "2024-03-15",
  "date_end": "2024-03-15",
  "price": "€15.00",
  "scraped_at": "2024-03-10T14:30:00"
}
```

## Configurazione

### Variabili d'Ambiente

| Variabile | Descrizione | Default |
|-----------|-------------|---------|
| `POSTGRES_HOST` | Host database | `localhost` |
| `POSTGRES_PORT` | Porta database | `5432` |
| `POSTGRES_DB` | Nome database | `events` |
| `POSTGRES_USER` | Utente database | `postgres` |
| `POSTGRES_PASSWORD` | Password database | `postgres` |
| `SCRAPY_LOG_LEVEL` | Livello log | `INFO` |
| `SCRAPY_CONCURRENT_REQUESTS` | Richieste concorrenti | `8` |
| `SCRAPY_DOWNLOAD_DELAY` | Delay tra richieste | `1.0` |

### Pipeline PostgreSQL

Per abilitare il salvataggio su PostgreSQL, modifica `settings.py`:

```python
ITEM_PIPELINES = {
    "events_scraper.pipelines.ValidationPipeline": 100,
    "events_scraper.pipelines.HashGeneratorPipeline": 200,
    "events_scraper.pipelines.PostgresPipeline": 300,  # Decommentare
}
```

## Sviluppo

### Struttura Progetto

```
service-scraping/
├── src/                  # Codice sorgente Scrapy
│   ├── items.py          # Definizione EventItem
│   ├── settings.py       # Configurazione Scrapy
│   ├── pipelines.py      # Pipeline elaborazione
│   ├── spiders/          # Spider specifici
│   │   ├── base.py       # Spider base (classe astratta)
│   │   ├── zero_eu.py    # Spider zero.eu
│   │   ├── city_today.py # Spider *Today.it
│   │   └── artribune.py  # Spider artribune.com
│   ├── scrapy.cfg        # Config Scrapy/Scrapyd
│   └── requirements.txt  # Dipendenze Python
├── venv/                 # Virtual environment locale
├── scrapyd.conf          # Config server Scrapyd
├── Dockerfile            # Immagine Docker
├── docker-compose.yml    # Compose per development
├── docker-entrypoint.sh  # Script di avvio container
├── templates.json        # Template configurazioni
└── README.md             # Questa documentazione
```

### Aggiungere un Nuovo Spider

1. Crea il file in `spiders/nuovo_spider.py`
2. Eredita da `BaseEventSpider`
3. Implementa `start_requests()` e i callback necessari
4. Usa `self.create_item()` per creare EventItem consistenti

```python
from events_scraper.spiders.base import BaseEventSpider

class NuovoSpider(BaseEventSpider):
    name = "nuovo"
    source_name = "nuovo_sito"
    allowed_domains = ["nuovo-sito.com"]

    def start_requests(self):
        yield scrapy.Request("https://nuovo-sito.com/eventi", callback=self.parse)

    def parse(self, response):
        # Estrazione eventi...
        item = self.create_item()
        item["title"] = response.css("h1::text").get()
        # ...
        yield item
```

### Test Locali

```bash
# Esegui spider con output JSON
scrapy crawl city_today -a cities=milano -o test_output.json

# Esegui con log dettagliato
scrapy crawl city_today -a cities=milano -L DEBUG

# Esegui in shell per debug
scrapy shell "https://www.milanotoday.it/eventi/"
```

## Integrazione con Airflow

Esempio DAG per schedulare gli spider:

```python
from airflow import DAG
from airflow.operators.http_operator import SimpleHttpOperator
from datetime import datetime

with DAG("events_scraping", start_date=datetime(2024, 1, 1), schedule_interval="0 6 * * *") as dag:

    scrape_milano = SimpleHttpOperator(
        task_id="scrape_milano",
        http_conn_id="scrapyd",
        endpoint="/schedule.json",
        method="POST",
        data={
            "project": "events_scraper",
            "spider": "city_today",
            "cities": "milano",
            "periodo": "oggi"
        }
    )
```

## Troubleshooting

### Spider non trovato

```bash
# Verifica che il progetto sia deployato
curl http://localhost:6800/listspiders.json?project=events_scraper

# Re-deploy manuale
cd /app && scrapyd-deploy
```

### Errori di connessione database

```bash
# Verifica variabili d'ambiente
docker compose exec scrapyd env | grep POSTGRES

# Test connessione
docker compose exec scrapyd python -c "import psycopg2; psycopg2.connect(host='postgres', dbname='events', user='postgres', password='postgres')"
```

### Rate limiting

Se un sito blocca le richieste, aumenta il delay:

```bash
curl http://localhost:6800/schedule.json \
  -d project=events_scraper \
  -d spider=city_today \
  -d cities=milano \
  -d setting=DOWNLOAD_DELAY=3
```

## License

MIT License
