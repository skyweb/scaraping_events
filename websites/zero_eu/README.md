# Zero.eu Events Scraper

Questo progetto è uno scraper basato su [Scrapy](https://scrapy.org/) per estrarre informazioni sugli eventi dal sito [Zero.eu](https://zero.eu).

## Prerequisiti

*   Python 3.11 o superiore
*   Virtualenv (consigliato)

## Installazione

1.  **Clona il repository o scarica i file.**

2. **Attiva l'ambiente virtuale:**



    Poiché la cartella `venv` è già presente, puoi attivarla direttamente:



    ```bash

    source venv/bin/activate

    ```



3. **Installa le dipendenze:**







    È possibile installare tutte le dipendenze necessarie utilizzando il file `requirements.txt`:



    ```bash



    pip install -r requirements.txt



    ```

## Utilizzo

Il progetto include uno script helper `run_spider.py` per facilitare l'esecuzione dello scraper.

### Esecuzione base

Per avviare lo scraper per la città di default (**Milano**):

```bash
python run_spider.py
```

### Specificare una città

Puoi specificare una città diversa passando il nome come argomento:

```bash
python run_spider.py bologna
python run_spider.py roma
python run_spider.py torino
```

*Città supportate (con fallback ID):* Milano, Bologna, Roma, Torino, Firenze, Venezia, Napoli.

## Output

Lo script genererà un file JSON nella cartella `output/` con il formato:

`output/eventi_zero_{città}_{timestamp}.json`

Esempio: `output/eventi_zero_milano_20260126_103000.json`

### Formato dei dati

Il file JSON conterrà un array di oggetti evento con i seguenti campi:
*   `title`: Titolo dell'evento
*   `description`: Descrizione (testo pulito)
*   `city`: Città
*   `location_name`: Nome del locale/luogo
*   `location_address`: Indirizzo (se disponibile)
*   `date_start`, `date_end`: Date di inizio e fine
*   `time_start`, `time_end`: Orari
*   `price`: Prezzo
*   `category`: Categoria evento
*   `image_url`: URL dell'immagine in evidenza
*   `url`: Link originale all'evento su Zero.eu

## Struttura del Progetto

*   `run_spider.py`: Script principale per lanciare il processo.
*   `zero_scraper/`: Modulo Scrapy contenente lo spider e le configurazioni.
    *   `spiders/events_spider.py`: Logica di scraping.
    *   `settings.py`: Impostazioni di Scrapy.
*   `scrapy.cfg`: File di configurazione di deploy di Scrapy.
