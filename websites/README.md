# Scrapy Events Docker Image

Questa immagine Docker contiene gli spider Scrapy per lo scraping degli eventi.

## Build dell'immagine

### Da docker-compose (consigliato)

```bash
cd infrastructures
docker compose build scrapy-events
```

### Build manuale

```bash
cd websites
docker build -t scrapy-events:latest .
```

## Utilizzo

### Spider city_today

Scraping eventi da *Today.it (Milano, Roma, Bologna, etc.)

```bash
# Singola città
$ docker run --rm -v $(pwd)/data:/data/output scrapy-events:latest city_today milano

# Con periodo specifico
$ docker run --rm -v $(pwd)/data:/data/output scrapy-events:latest city_today roma --periodo=questa-settimana
```

**Periodi disponibili:**
- `oggi`
- `domani`
- `weekend`
- `questa-settimana` (default)
- `prossima-settimana`
- `questo-mese`

### Spider zero_eu

Scraping eventi da Zero.eu

```bash
$ docker run --rm -v $(pwd)/data:/data/output scrapy-events:latest zero_eu milano
```

## Città supportate

| Città | city_today | zero_eu |
|-------|:---:|:---:|
| Milano | ✅ | ✅ |
| Torino | ✅ | ✅ |
| Genova | ✅ | ❌ |
| Venezia | ✅ | ✅ |
| Bologna | ✅ | ✅ |
| Verona | ✅ | ❌ |
| Treviso | ✅ | ❌ |
| Trento | ✅ | ❌ |
| Udine | ✅ | ❌ |
| Pordenone | ✅ | ❌ |
| Vicenza | ✅ | ❌ |
| Padova | ✅ | ❌ |
| Monza | ✅ | ❌ |
| Lecco | ✅ | ❌ |
| Sondrio | ✅ | ❌ |
| Novara | ✅ | ❌ |
| Brescia | ✅ | ❌ |
| Parma | ✅ | ❌ |
| Rimini | ✅ | ❌ |
| Ravenna | ✅ | ❌ |
| Forlì | ✅ | ❌ |
| Cesena | ✅ | ❌ |
| Como | ✅ | ❌ |
| Piacenza | ✅ | ❌ |
| Trieste | ✅ | ❌ |
| Roma | ✅ | ✅ |
| Firenze | ✅ | ✅ |
| Pisa | ✅ | ❌ |
| Livorno | ✅ | ❌ |
| Perugia | ✅ | ❌ |
| Terni | ✅ | ❌ |
| Ancona | ✅ | ❌ |
| Latina | ✅ | ❌ |
| Frosinone | ✅ | ❌ |
| Viterbo | ✅ | ❌ |
| Arezzo | ✅ | ❌ |
| Pescara | ✅ | ❌ |
| Napoli | ✅ | ✅ |
| Palermo | ✅ | ❌ |
| Catania | ✅ | ❌ |
| Messina | ✅ | ❌ |
| Bari | ✅ | ❌ |
| Foggia | ✅ | ❌ |
| Salerno | ✅ | ❌ |
| Avellino | ✅ | ❌ |
| Reggio Calabria | ✅ | ❌ |
| Lecce | ✅ | ❌ |
| Brindisi | ✅ | ❌ |
| Agrigento | ✅ | ❌ |
| Caserta | ✅ | ❌ |

## Output

I file JSON vengono salvati in `/data/output` con naming:
- `eventi_{city}_{periodo}_{timestamp}.json` (city_today)
- `eventi_zero_{city}_{timestamp}.json` (zero_eu)

## Struttura progetto

```
websites/
├── Dockerfile
├── requirements.txt
├── entrypoint.sh
├── city_today/          # Spider per *Today.it
│   └── events/
│       └── spiders/
│           └── events_spider.py
└── zero_eu/             # Spider per Zero.eu
    └── zero_scraper/
        └── spiders/
            └── events_spider.py
```
