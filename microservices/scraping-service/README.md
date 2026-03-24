# Events Scraper

Progetto Scrapy per lo scraping di eventi da diverse fonti italiane.

## Spider Disponibili

### Aggregatori nazionali

| Spider | Fonte | Descrizione |
|--------|-------|-------------|
| `city_today` | Rete *Today.it | 50+ citta italiane (MilanoToday, RomaToday, etc.) |
| `zero_eu` | [zero.eu](https://zero.eu) | Eventi culturali (concerti, mostre, teatro) |
| `artribune` | [artribune.com](https://artribune.com) | Mostre d'arte e eventi culturali |

### Portali turistici regionali

| Spider | Regione | Fonte |
|--------|---------|-------|
| `love_vda` | Valle d'Aosta | lovevda.it |
| `in_lombardia` | Lombardia | in-lombardia.it |
| `visit_trentino` | Trentino | visittrentino.info |
| `suedtirol` | Alto Adige | suedtirol.info |
| `veneto_eu` | Veneto | veneto.eu |
| `turismo_fvg` | Friuli Venezia Giulia | turismofvg.it |
| `la_mia_liguria` | Liguria | lamialiguria.it |
| `visit_tuscany` | Toscana | visittuscany.com |
| `umbria_tourism` | Umbria | umbriatourism.it |
| `lets_marche` | Marche | turismo.marche.it |
| `visit_lazio` | Lazio | visitlazio.com |
| `abruzzo_turismo` | Abruzzo | abruzzoturismo.it |
| `in_campania` | Campania | incampania.com |
| `puglia_culture` | Puglia | pugliaculture.it |
| `viaggiare_in_puglia` | Puglia | viaggiareinpuglia.it |
| `basilicata_turistica` | Basilicata | basilicataturistica.it |
| `visit_sicily` | Sicilia | visitsicily.info |
| `sardegna_turismo` | Sardegna | sardegnaturismo.it |

### Portali turistici per citta

| Spider | Citta | Fonte |
|--------|-------|-------|
| `turismo_torino` | Torino | turismotorino.org |
| `yes_milano` | Milano | yesmilano.it |
| `visit_verona` | Verona | visitverona.it |
| `venezia_unica` | Venezia | veneziaunica.it |
| `visit_modena` | Modena | visitmodena.it |
| `turismo_pisa` | Pisa | turismo.pisa.it |
| `siena_comunica` | Siena | sienacomunica.it |
| `comune_lucca` | Lucca | comune.lucca.it |
| `feel_florence` | Firenze | feelflorence.it |
| `turismo_roma` | Roma | turismoroma.it |

## Quick Start

### Con Docker (sviluppo)

```bash
# Build e avvio Scrapyd server
docker compose up -d

# Verifica che sia attivo
curl http://localhost:6800/daemonstatus.json

# Esegui uno spider
docker compose exec scrapyd scrapy crawl city_today -a cities=milano
```

### Senza Docker

```bash
cd microservices/scraping-service

python -m venv venv
source venv/bin/activate
pip install -r src/requirements.txt

cd src
scrapy crawl city_today -a cities=milano -o milano.json
```

### Build e push su Harbor Registry

```bash
cd infrastructures

# Build immagine
make registry-build

# Push su registry.${DOMAIN}
make registry-login
make registry-push
```

## Anti-Detection

Il servizio include due middleware per evitare blocchi durante lo scraping.

### User-Agent Rotation

Attivo di default. Ogni richiesta usa un User-Agent casuale tra Chrome, Firefox, Safari e Edge su Windows e Mac.

Configurato in `settings.py`:

```python
DOWNLOADER_MIDDLEWARES = {
    "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
    "middlewares.RandomUserAgentMiddleware": 400,
}
```

Per aggiungere User-Agent personalizzati:

```python
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ...",
]
```

### Proxy Rotation

Disabilitato di default. Si attiva tramite variabili d'ambiente o settings.

#### Attivazione globale (tutti gli spider)

```bash
# .env
PROXY_ENABLED=true
PROXY_LIST=http://proxy1:8080,http://user:pass@proxy2:8080,socks5://proxy3:1080
```

#### Attivazione da file

```bash
# .env
PROXY_ENABLED=true
PROXY_LIST_FILE=/data/proxies.txt
```

Il file contiene un proxy per riga (le righe vuote e quelle che iniziano con `#` vengono ignorate):

```
# Pool datacenter EU
http://proxy1.example.com:8080
http://user:pass@proxy2.example.com:3128
socks5://proxy3.example.com:1080

# Pool residenziale
http://user:pass@residential.example.com:9090
```

#### Attivazione per singolo spider

```python
class MySpider(scrapy.Spider):
    name = "my_spider"
    custom_settings = {
        "PROXY_ENABLED": True,
        "PROXY_LIST": "http://proxy1:8080,http://proxy2:8080",
    }
```

#### Skip proxy per singola richiesta

```python
yield scrapy.Request(url, meta={"no_proxy": True})
```

#### Formati proxy supportati

| Formato | Esempio |
|---------|---------|
| HTTP | `http://host:port` |
| HTTP con auth | `http://user:pass@host:port` |
| SOCKS5 | `socks5://host:port` |
| SOCKS5 con auth | `socks5://user:pass@host:port` |

#### Gestione errori proxy

Il middleware tiene traccia degli errori per ogni proxy. Dopo 5 errori consecutivi un proxy viene escluso dalla rotazione. Se tutti i proxy vengono esclusi, i contatori vengono resettati e si riprova con l'intera lista.

#### Servizi proxy compatibili

Qualsiasi servizio che espone un endpoint HTTP/SOCKS5 funziona. Esempi:

| Servizio | Tipo | Configurazione |
|----------|------|----------------|
| ScraperAPI | Rotating endpoint | `PROXY_LIST=http://api_key:@proxy-server.scraperapi.com:8001` |
| Bright Data | Pool residenziale | `PROXY_LIST=http://user:pass@zproxy.lum-superproxy.io:22225` |
| Smartproxy | Datacenter/residenziale | `PROXY_LIST=http://user:pass@gate.smartproxy.com:7000` |
| Lista libera | Pubblici (meno affidabili) | `PROXY_LIST=http://1.2.3.4:8080,http://5.6.7.8:3128` |

## Utilizzo con Scrapyd

### Dashboard

Dopo l'avvio: http://localhost:6800

### API Endpoints

```bash
# Schedulare uno spider
curl http://localhost:6800/schedule.json \
  -d project=events_scraper \
  -d spider=city_today \
  -d cities=roma \
  -d periodo=weekend \
  -d max_pages=5

# Lista job attivi
curl http://localhost:6800/listjobs.json?project=events_scraper

# Stato daemon
curl http://localhost:6800/daemonstatus.json

# Cancellare job
curl http://localhost:6800/cancel.json \
  -d project=events_scraper \
  -d job=JOB_ID
```

## Parametri Spider

### city_today

| Parametro | Descrizione | Default |
|-----------|-------------|---------|
| `cities` | Lista citta separate da virgola | Tutte |
| `periodo` | Filtro temporale | `questa-settimana` |

**Periodi:** `oggi`, `domani`, `weekend`, `questa-settimana`, `prossima-settimana`, `questo-mese`

### zero_eu

| Parametro | Descrizione | Default |
|-----------|-------------|---------|
| `city` | Slug citta | `milano` |

**Citta:** milano, roma, bologna, torino, firenze, venezia, napoli

### Spider regionali / citta

| Parametro | Descrizione | Default |
|-----------|-------------|---------|
| `max_pages` | Numero massimo pagine listing | `5`-`15` (varia per spider) |

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
  "price": "15.00",
  "scraped_at": "2024-03-10T14:30:00"
}
```

## Configurazione

### Variabili d'Ambiente

| Variabile | Descrizione | Default |
|-----------|-------------|---------|
| `SCRAPY_LOG_LEVEL` | Livello log | `INFO` |
| `SCRAPY_CONCURRENT_REQUESTS` | Richieste concorrenti | `8` |
| `SCRAPY_CONCURRENT_REQUESTS_PER_DOMAIN` | Richieste concorrenti per dominio | `2` |
| `SCRAPY_DOWNLOAD_DELAY` | Delay tra richieste (secondi) | `1.0` |
| `API_BASE_URL` | URL backoffice API | `http://localhost:8000` |
| `API_CLIENT_ID` | OAuth2 client ID | - |
| `API_CLIENT_SECRET` | OAuth2 client secret | - |
| `KEYCLOAK_TOKEN_URL` | Token endpoint Keycloak | `http://keycloak:8080/realms/today-events/...` |
| `PROXY_ENABLED` | Abilita proxy rotation | `false` |
| `PROXY_LIST` | Lista proxy (separati da virgola) | - |
| `PROXY_LIST_FILE` | File con proxy (uno per riga) | - |
| `OTEL_ENABLED` | Abilita tracing OpenTelemetry | `false` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Endpoint OTel Collector | `http://localhost:4317` |

## Integrazione con Airflow

L'immagine Docker viene pullata dal registry Harbor e lanciata da Airflow tramite `DockerOperator` con autenticazione automatica via robot account.

DAG disponibili in `infrastructures/services/airflow/dags/`:

| DAG | Schedule | Descrizione |
|-----|----------|-------------|
| `etl_events_daily` | Ogni giorno alle 6:00 | Scraping eventi questa settimana |
| `etl_events_weekly` | Domenica alle 8:00 | Scraping eventi prossima settimana |
| `etl_events_monthly` | 1 del mese alle 4:00 | Scraping eventi questo mese |

## Struttura Progetto

```
scraping-service/
├── src/
│   ├── spiders/             # 30+ spider (base, city, regionali)
│   │   ├── base.py          # Spider base (classe astratta)
│   │   ├── city_today.py    # Spider *Today.it
│   │   ├── zero_eu.py       # Spider zero.eu
│   │   ├── artribune.py     # Spider artribune.com
│   │   └── ...              # Spider regionali e per citta
│   ├── items.py             # Definizione EventItem
│   ├── settings.py          # Configurazione Scrapy
│   ├── middlewares.py       # RandomUserAgent + RotatingProxy
│   ├── pipelines.py         # Pipeline (Validation, API, BatchExport)
│   ├── scrapy.cfg           # Config Scrapy/Scrapyd
│   ├── requirements.txt     # Dipendenze Python
│   ├── Dockerfile           # Immagine produzione
│   └── Dockerfile.dev       # Immagine sviluppo
├── data/                    # Output e log
├── docker-compose.yml       # Compose per development
├── docker-entrypoint.sh     # Script di avvio container
└── .env                     # Variabili d'ambiente
```

## Sviluppo

### Aggiungere un Nuovo Spider

1. Crea il file in `src/spiders/nuovo_spider.py`
2. Eredita da `BaseEventSpider`
3. Implementa `start_requests()` e i callback necessari
4. Usa `self.create_item()` per creare EventItem consistenti

```python
from spiders.base import BaseEventSpider

class NuovoSpider(BaseEventSpider):
    name = "nuovo"
    source_name = "nuovo_sito"
    allowed_domains = ["nuovo-sito.com"]

    def start_requests(self):
        yield scrapy.Request("https://nuovo-sito.com/eventi", callback=self.parse)

    def parse(self, response):
        item = self.create_item()
        item["title"] = response.css("h1::text").get()
        yield item
```

### Test Locali

```bash
# Esegui spider con output JSON
scrapy crawl city_today -a cities=milano -o test_output.json

# Esegui con log dettagliato
scrapy crawl city_today -a cities=milano -L DEBUG

# Shell interattiva per debug CSS/XPath
scrapy shell "https://www.milanotoday.it/eventi/"

# Test con proxy attivi
PROXY_ENABLED=true PROXY_LIST=http://proxy:8080 scrapy crawl city_today -a cities=milano
```

## Troubleshooting

### Spider non trovato

```bash
# Verifica che il progetto sia deployato
curl http://localhost:6800/listspiders.json?project=events_scraper

# Re-deploy manuale
cd /app && scrapyd-deploy
```

### Rate limiting / IP bloccato

1. Aumenta il delay tra richieste:
   ```bash
   SCRAPY_DOWNLOAD_DELAY=3 scrapy crawl city_today -a cities=milano
   ```

2. Abilita proxy rotation:
   ```bash
   PROXY_ENABLED=true PROXY_LIST=http://proxy1:8080,http://proxy2:8080 scrapy crawl city_today -a cities=milano
   ```

3. Verifica i log per errori proxy:
   ```
   WARNING: Proxy http://proxy1:8080 errore (3/5): ConnectionRefusedError
   ```

### Errori di connessione database

```bash
# Verifica variabili d'ambiente
docker compose exec scrapyd env | grep POSTGRES

# Test connessione
docker compose exec scrapyd python -c "
import psycopg2
psycopg2.connect(host='postgres', dbname='today_events', user='events', password='events_secret_2026')
print('OK')
"
```
