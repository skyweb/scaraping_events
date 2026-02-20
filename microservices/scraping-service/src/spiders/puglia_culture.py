# -*- coding: utf-8 -*-
"""
Spider per pugliaculture.it - Portale eventi culturali della Puglia.

Il sito usa WordPress con Elementor come page builder.
Il contenuto strutturato (date, luogo, prezzo, cast) è nei blocchi
div.elementor-text-editor; il content.rendered dell'API REST è vuoto.

Strategia:
- WP REST API (/wp-json/wp/v2/evento) per il listing con paginazione nativa
  (header X-WP-TotalPages, 100 eventi/pagina)
- HTML scraping della pagina dettaglio per estrarre:
  - Cast / descrizione artistica  → blocco elementor-text-editor con <strong>Cast</strong>
  - COSTI E INFO                  → blocco elementor-text-editor con <strong>COSTI</strong>
  - Teatro / location             → <p><strong>Teatro:</strong> ...</p>
  - Date e orari                  → <ul><li> con span mesi italiani + "H:"
  - Categoria                     → link /categoria/
- Immagine da yoast_head_json.og_image nell'API

Utilizzo:
    # Prime N pagine API (default: 5, 100 eventi/pagina)
    scrapy crawl puglia_culture -o output.json

    # Con limite pagine
    scrapy crawl puglia_culture -a max_pages=35 -o output.json

    # Scrapyd
    curl http://localhost:6800/schedule.json \
        -d project=events_scraper \
        -d spider=puglia_culture \
        -d max_pages=10

Parametri:
    max_pages: Numero massimo di pagine API (default: 5, ~35 pagine totali)
"""

import json
import re
from datetime import datetime
from typing import Optional

import scrapy

from spiders.base import BaseEventSpider


# Mappa mesi italiani → numero mese
MESI_IT = {
    'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4,
    'maggio': 5, 'giugno': 6, 'luglio': 7, 'agosto': 8,
    'settembre': 9, 'ottobre': 10, 'novembre': 11, 'dicembre': 12,
}

API_URL = "https://www.pugliaculture.it/wp-json/wp/v2/evento"


def parse_italian_date_time(text: str) -> tuple:
    """
    Converte una stringa data/ora italiana in (YYYY-MM-DD, HH:MM).

    Gestisce:
    - "venerdì 13 marzo 2026 H: 21:00"
    - "venerdì 13 marzo 2026H: 21:00"   (senza spazio prima di H:)
    - "venerdì 13 marzo 2026"
    - "13 marzo 2026"
    - "13 marzo"

    Returns:
        Tupla (data YYYY-MM-DD o None, ora HH:MM o None)
    """
    text = text.strip()

    # Estrai orario se presente (es: "H: 21:00", "H:21:00", "H 21:00")
    time_match = re.search(r"H:?\s*(\d{1,2}:\d{2})", text, re.IGNORECASE)
    time_str = time_match.group(1) if time_match else None
    # Rimuovi la parte orario per parsare la data
    date_text = re.sub(r"H:?\s*\d{1,2}:\d{2}", "", text, flags=re.IGNORECASE).strip()

    parts = date_text.lower().split()
    # Rimuovi giorno della settimana se la prima parola non è un numero
    if parts and not parts[0][0].isdigit():
        parts = parts[1:]

    if len(parts) < 2:
        return None, time_str

    try:
        day = int(parts[0])
        month = MESI_IT.get(parts[1])
        if not month:
            return None, time_str
        year = int(parts[2]) if len(parts) >= 3 else datetime.now().year
        return f"{year:04d}-{month:02d}-{day:02d}", time_str
    except (ValueError, IndexError):
        return None, time_str


class PugliaCultureSpider(BaseEventSpider):
    """
    Spider per pugliaculture.it.

    Usa la WP REST API per il listing e HTML scraping Elementor per i dettagli.
    Estrae: cast/descrizione artistica, costi e info, teatro, date multiple, categoria.
    """

    name = "puglia_culture"
    source_name = "puglia_culture"
    allowed_domains = ["www.pugliaculture.it", "pugliaculture.it"]

    custom_settings = {
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "ROBOTSTXT_OBEY": True,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.5,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
    }

    def __init__(self, max_pages: str = "5", *args, **kwargs):
        """
        Inizializza lo spider.

        Args:
            max_pages: Numero massimo di pagine API (default: 5 × 100 = 500 eventi)
        """
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self._seen_urls: set = set()

    def start_requests(self):
        """Prima richiesta all'API WordPress."""
        url = f"{API_URL}?per_page=100&page=1&_fields=id,slug,link,title,yoast_head_json"
        yield scrapy.Request(url, callback=self.parse_api, meta={"page": 1})

    def parse_api(self, response):
        """
        Parsa la risposta JSON dell'API WordPress.
        Legge X-WP-TotalPages dagli header per gestire la paginazione.

        Args:
            response: Risposta HTTP con JSON array di eventi
        """
        try:
            events = json.loads(response.text)
        except (json.JSONDecodeError, ValueError):
            self.logger.error(f"Risposta API non valida: {response.url}")
            return

        if not events:
            return

        # Yield richieste per le pagine successive (solo dalla prima pagina)
        current_page = response.meta.get("page", 1)
        if current_page == 1:
            total_pages = int(response.headers.get("X-WP-TotalPages", 1))
            pages_to_fetch = min(total_pages, self.max_pages)
            self.logger.info(f"Totale pagine API: {total_pages}, fetching: {pages_to_fetch}")
            for page in range(2, pages_to_fetch + 1):
                url = f"{API_URL}?per_page=100&page={page}&_fields=id,slug,link,title,yoast_head_json"
                yield scrapy.Request(url, callback=self.parse_api, meta={"page": page})

        # Yield richieste HTML per ogni evento
        for event in events:
            detail_url = event.get("link")
            if not detail_url or detail_url in self._seen_urls:
                continue
            self._seen_urls.add(detail_url)

            # Immagine da Yoast og_image
            yoast = event.get("yoast_head_json") or {}
            og_images = yoast.get("og_image") or []
            image_url = og_images[0].get("url") if og_images else None

            title_rendered = (event.get("title") or {}).get("rendered", "")

            yield scrapy.Request(
                detail_url,
                callback=self.parse_event_detail,
                meta={
                    "event_id": str(event.get("id", "")),
                    "slug": event.get("slug", ""),
                    "image_url_api": image_url,
                    "title_api": self.clean_text(title_rendered),
                },
            )

    def parse_event_detail(self, response):
        """
        Parsa la pagina HTML di dettaglio evento (Elementor).

        Estrae:
        - Titolo (h1)
        - Categoria (link /categoria/)
        - Date multiple + orario (ul/li con mesi italiani)
        - Location/Teatro (<p><strong>Teatro:</strong>...)
        - Descrizione artistica (blocco elementor-text-editor con Cast)
        - Prezzo (dal blocco COSTI E INFO)
        - Raw info COSTI E INFO completo

        Args:
            response: Risposta HTTP della pagina dettaglio
        """
        # ── Titolo ────────────────────────────────────────────────────────────
        title = (
            self.clean_text(response.css("h1::text").get())
            or response.meta.get("title_api")
        )

        # ── Immagine ──────────────────────────────────────────────────────────
        image_url = (
            response.meta.get("image_url_api")
            or response.xpath('//meta[@property="og:image"]/@content').get()
        )

        # ── Categoria ─────────────────────────────────────────────────────────
        category = self._extract_category(response)

        # ── Date e orari ──────────────────────────────────────────────────────
        date_info = self._extract_dates(response)
        date_start = date_info.get("date_start")
        date_end = date_info.get("date_end")
        date_display = date_info.get("display")
        time_start = date_info.get("time_start")

        # ── Luogo (Teatro) ────────────────────────────────────────────────────
        location_name = self._extract_location(response)

        # ── Descrizione artistica (Cast) ──────────────────────────────────────
        description = self._extract_description(response)

        # ── COSTI E INFO (blocco completo) ────────────────────────────────────
        costi_info = self._extract_costi_info(response)
        price = self._extract_price_from_costi(costi_info)
        website = self._extract_website_from_costi(response)

        slug = response.meta.get("slug") or response.url.rstrip("/").split("/")[-1]

        item = self.create_item(
            url=response.url,
            title=title,
            description=description,
            date_start=date_start,
            date_end=date_end,
            date_display=date_display,
            time_start=time_start,
            location_name=location_name,
            image_url=image_url,
            category=category,
            price=price,
            website=website,
            slug=slug,
            event_id=response.meta.get("event_id", slug),
            raw_data={"costi_info": costi_info},
        )

        item["uuid"] = self.generate_uuid(
            item.get("title", ""),
            item.get("date_start", ""),
            item.get("location_name", ""),
        )
        item["content_hash"] = self.generate_content_hash(
            item.get("description", ""),
            item.get("price", ""),
            item.get("time_start", ""),
        )

        self.log_stats(item.get("city"))
        yield item

    # =========================================================================
    # METODI ESTRAZIONE HTML
    # =========================================================================

    def _extract_dates(self, response) -> dict:
        """
        Estrae date e orari dall'HTML.

        Struttura reale della pagina:
            <li>
              <div>13</div>
              <div>venerdì 13 marzo 2026H: 21:00</div>
            </li>

        La data + orario sono concatenati senza spazio nel secondo div.
        Prende la prima data come date_start e l'ultima come date_end.

        Returns:
            Dict con: date_start, date_end (YYYY-MM-DD), time_start (HH:MM), display
        """
        result = {"date_start": None, "date_end": None, "time_start": None, "display": None}

        parsed_dates = []
        first_time = None

        # Ogni <li> con un div figlio che contiene un mese italiano
        for li in response.xpath("//li[div]"):
            divs = li.css("div::text").getall()
            # Il testo con la data è solitamente nel secondo div
            date_text = None
            for div_text in divs:
                dt = self.clean_text(div_text) or ""
                if any(m in dt.lower() for m in MESI_IT):
                    date_text = dt
                    break

            if not date_text:
                continue

            parsed_date, parsed_time = parse_italian_date_time(date_text)
            if not parsed_date:
                continue

            parsed_dates.append(parsed_date)
            if first_time is None and parsed_time:
                first_time = parsed_time

        if parsed_dates:
            result["date_start"] = parsed_dates[0]
            result["time_start"] = first_time
            last_date = parsed_dates[-1]
            result["date_end"] = last_date if last_date != parsed_dates[0] else None
            result["display"] = (
                parsed_dates[0] if not result["date_end"]
                else f"{parsed_dates[0]} - {last_date}"
            )

        return result

    def _extract_location(self, response) -> Optional[str]:
        """
        Estrae il nome del luogo/teatro da div.event-teatro.

        Il blocco ha testo del tipo:
            "Teatro: Teatro Paolo Grassi - Cisternino"

        Returns:
            Nome venue (es: "Teatro Paolo Grassi - Cisternino") o None
        """
        block = response.css("div.event-teatro")
        if block:
            text = self.clean_text(block[0].xpath("string()").get())
            if text:
                # Rimuovi il prefisso "Teatro:" o "Luogo:"
                cleaned = re.sub(
                    r"^(Teatro|Luogo|Venue)[:\s]+", "", text, flags=re.IGNORECASE
                ).strip()
                return self.clean_text(cleaned) or None
        return None

    def _extract_description(self, response) -> Optional[str]:
        """
        Estrae la descrizione artistica dall'HTML.

        Usa il blocco div.event_cast che contiene il cast e le note di regia.

        Returns:
            Testo descrizione artistica o None
        """
        block = response.css("div.event_cast")
        if block:
            text = self.clean_text(block[0].xpath("string()").get())
            if text and len(text) > 10:
                return text
        return None

    def _extract_costi_info(self, response) -> Optional[str]:
        """
        Estrae il blocco completo "COSTI E INFO" da div.event_costi.

        Returns:
            Testo completo del blocco costi/info o None
        """
        block = response.css("div.event_costi")
        if block:
            text = self.clean_text(block[0].xpath("string()").get())
            if text:
                return text
        return None

    def _extract_price_from_costi(self, costi_text: Optional[str]) -> Optional[str]:
        """
        Estrae un riassunto prezzo dal testo "COSTI E INFO".

        Raccoglie le righe con valori €.

        Returns:
            Stringhe con prezzi uniti, es: "intero € 15 / ridotto € 10"
        """
        if not costi_text:
            return None

        price_lines = []
        for line in costi_text.split("\n"):
            line = line.strip()
            if re.search(r"€\s*\d", line) and len(line) < 80:
                price_lines.append(line)

        if price_lines:
            return " / ".join(price_lines)

        # Fallback: cerca qualsiasi pattern € direttamente nel testo
        matches = re.findall(r"[^\n]{0,30}€\s*[\d,]+[^\n]{0,20}", costi_text)
        if matches:
            return " / ".join(m.strip() for m in matches[:3])

        return None

    def _extract_website_from_costi(self, response) -> Optional[str]:
        """
        Estrae il sito web esterno se presente nella pagina (es: vivaticket.com).

        Returns:
            URL del sito esterno o None
        """
        external = response.xpath(
            '//a[starts-with(@href, "http") '
            'and not(contains(@href, "pugliaculture.it"))]/@href'
        ).get()
        return external or None

    def _extract_category(self, response) -> list:
        """
        Estrae le categorie dai link /categoria/ presenti nella pagina.

        Returns:
            Lista di categorie deduplicata (può essere vuota)
        """
        cats = response.css('a[href*="/categoria/"]::text').getall()
        cats = [self.clean_text(c) for c in cats if self.clean_text(c)]
        seen: set = set()
        unique = []
        for c in cats:
            if c not in seen:
                seen.add(c)
                unique.append(c)
        return unique
