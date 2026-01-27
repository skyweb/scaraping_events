# Milano Today Events Scraper

Progetto Scrapy per estrarre gli eventi da [MilanoToday.it](https://www.milanotoday.it/eventi/).

## Struttura del progetto

```
milano_today/scraping/
├── venv/                    # Virtual environment
├── milano_events/           # Progetto Scrapy
│   ├── spiders/
│   │   └── events_spider.py # Spider principale
│   ├── items.py             # Definizione item evento
│   └── settings.py          # Configurazioni Scrapy
├── run_spider.py            # Script per eseguire lo spider
└── README.md
```

## Installazione

```bash
# Attiva il virtual environment
source venv/bin/activate

# Le dipendenze sono già installate (scrapy)
```

## Utilizzo

### Eseguire lo spider

```bash
# Attiva l'ambiente virtuale
source venv/bin/activate

# Metodo 1: Usa lo script Python
python run_spider.py

# Metodo 2: Usa il comando Scrapy direttamente
scrapy crawl events -o eventi.json
```

### Output

Lo spider genera un file JSON con timestamp, es: `eventi_milano_20260125_123456.json`

## Dati estratti

Ogni evento contiene i seguenti campi:

| Campo | Descrizione |
|-------|-------------|
| `url` | URL della pagina dell'evento |
| `title` | Titolo dell'evento |
| `category` | Categoria (Cinema, Mostre, Concerti, etc.) |
| `image_url` | URL dell'immagine |
| `location_name` | Nome del luogo |
| `location_address` | Indirizzo |
| `date_start` | Data inizio (DD/MM/YYYY) |
| `date_end` | Data fine (DD/MM/YYYY) |
| `time_info` | Informazioni orario |
| `price` | Prezzo o "Gratis" |
| `description` | Descrizione completa |
| `website` | Sito web ufficiale |
| `scraped_at` | Timestamp dello scraping |

## Esempio output

```json
{
  "url": "https://www.milanotoday.it/eventi/tech-si-gira.html",
  "title": "\"Tech, si gira!\", a STEP FuturAbility District...",
  "category": "Cinema",
  "image_url": "//citynews-milanotoday.stgy.ovh/~media/...",
  "location_name": "STEP - Futurability District",
  "location_address": "Piazza Adriano Olivetti, 1",
  "date_start": "29/01/2026",
  "date_end": "26/11/2026",
  "time_info": "Vedi programma completo sul sito",
  "price": "Gratis",
  "description": "Al via nel cuore di Milano un'imperdibile rassegna...",
  "website": "https://www.steptothefuture.it/...",
  "scraped_at": "2026-01-25T23:19:50.510354"
}
```

## Note tecniche

- Lo spider rispetta il `robots.txt` del sito
- Delay di 1 secondo tra le richieste per non sovraccaricare il server
- Gestisce contenuti lazy-loaded (caricamento asincrono)
- I dettagli dell'evento variano in base alla struttura della pagina sorgente
