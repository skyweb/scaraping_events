# -*- coding: utf-8 -*-
"""
Spider per pugliaculture.it - Portale eventi culturali della Puglia.

Il sito usa WordPress con Elementor come page builder.
Il contenuto strutturato (date, luogo, prezzo, cast) è nei blocchi

Strategia:
- WP REST API per il listing con paginazione nativa su 4 endpoint:
  /wp-json/wp/v2/evento, spettacolo, teatro, rassegna
- HTML scraping della pagina dettaglio per estrarre i dati strutturati
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
from typing import Optional

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS, MESI_IT, parse_italian_date_time

API_BASE = "https://www.pugliaculture.it/wp-json/wp/v2"
API_ENDPOINTS = ("evento", "spettacolo", "rassegna")


class PugliaCultureSpider(BaseEventSpider):
    """
    Spider per pugliaculture.it.

    Usa la WP REST API per il listing e HTML scraping Elementor per i dettagli.
    """

    name = "puglia_culture"
    source_name = "puglia_culture"
    allowed_domains = ["www.pugliaculture.it", "pugliaculture.it"]

    custom_settings = {**DEFAULT_CRAWL_SETTINGS}

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
        """Prima richiesta all'API WordPress per ogni endpoint (evento, spettacolo, rassegna)."""
        for cpt in API_ENDPOINTS:
            url = f"{API_BASE}/{cpt}?per_page=100&page=1&_fields=id,slug,link,title,yoast_head_json"
            yield scrapy.Request(
                url, callback=self.parse_api, meta={"page": 1, "cpt": cpt}
            )

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
        cpt = response.meta.get("cpt", "evento")
        current_page = response.meta.get("page", 1)
        if current_page == 1:
            total_pages = int(response.headers.get("X-WP-TotalPages", 1))
            pages_to_fetch = min(total_pages, self.max_pages)
            self.logger.info(f"[{cpt}] Totale pagine API: {total_pages}, fetching: {pages_to_fetch}")
            for page in range(2, pages_to_fetch + 1):
                url = f"{API_BASE}/{cpt}?per_page=100&page={page}&_fields=id,slug,link,title,yoast_head_json"
                yield scrapy.Request(url, callback=self.parse_api, meta={"page": page, "cpt": cpt})

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
                    "image_url_api": image_url,
                    "title_api": self.clean_text(title_rendered),
                    "cpt": cpt,
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
        date_end = date_info.get("date_end") or date_start
        date_display = response.css("div.event-dates").get()

        # ── Luogo  ────────────────────────────────────────────────────
        location_name = self._extract_location(response)

        # ── City name: parte dopo " - " in location_name ──────────────────────
        # es: "Teatro Comunale di Nardò - Nardò" → "Nardò"
        city_name = None
        if location_name and " - " in location_name:
            parts = location_name.rsplit(" - ", 1)
            location_name = parts[0].strip() or location_name
            city_name = parts[-1].strip() or None

        # ── Descrizione (HTML grezzo da div.spettacolo-content) ───────────────
        description = self._extract_description(response)

        # ── COSTI E INFO (blocco completo) ────────────────────────────────────
        costi_info = self._extract_costi_info(response)

        # ── Section annidato ────────────────────
        section_data = {}
        events_dati_html = response.css("div.events_dati").get()
        if events_dati_html:
            section_data["events_dati"] = events_dati_html
        cast_html = response.css("div.event_cast").get()
        if cast_html:
            section_data["casting"] = cast_html
        rassegna_html = response.css("div.event-rassegna").get()
        if rassegna_html:
            section_data["rassegna"] = rassegna_html

        # ── Costi e contatti → section ────────────────────────────────────────
        if costi_info:
            section_data["info_e_costi"] = costi_info
        contatti_html = response.css("div.events_info_e_contatti").get()
        if contatti_html:
            section_data["info_e_contatti"] = contatti_html

        uuid = self.generate_uuid(title, date_start, location_name)
        content_hash = self.generate_content_hash(description)

        item = self.create_item(
            uuid=uuid,
            title=title,
            data={
                # Contenuto
                "description": description,
                "category": category,
                "image_url": image_url,
                # Date e orari
                "dates": {
                    "date_start": date_start or "",
                    "date_end": date_end or "",
                    "date_display": date_display or "",
                },
                # Location
                "city": {
                    "city_name": city_name or "",
                    "location_name": location_name or "",
                },
                # Dettagli
                "section": section_data or None,
            },
            meta={
                "content_hash": content_hash,
                "url": response.url,
                "category": response.meta.get("cpt", "evento"),
            },
        )

        yield item

    # =========================================================================
    # METODI ESTRAZIONE HTML
    # =========================================================================

    def _extract_dates(self, response) -> dict:
        """
        Estrae date e orari dall'HTML.

        Struttura reale della pagina:
            <li class="single_data">
              <div class="giorno_esteso">04<br>febbraio</div>
              <div class="data_event_single">
                mercoledì 04 febbraio 2026
                <strong>H: 10:00</strong>
              </div>
            </li>

        Returns:
            Dict con: date_start, date_end (YYYY-MM-DD HH:MM).
            Se date_end non trovata, uguale a date_start.
        """
        result = {"date_start": None, "date_end": None}

        entries = []  # lista di (date_str "YYYY-MM-DD", time_str "HH:MM" o None)

        for li in response.css("li.single_data"):
            date_text = self.clean_text(
                li.css("div.data_event_single::text").get() or ""
            )
            time_text = self.clean_text(
                li.css("div.data_event_single strong::text").get() or ""
            )

            combined = f"{date_text} {time_text}".strip()
            if not any(m in combined.lower() for m in MESI_IT):
                continue

            parsed_date, parsed_time = parse_italian_date_time(combined)
            if not parsed_date:
                continue

            entries.append((parsed_date, parsed_time))

        if entries:
            first_date, first_time = entries[0]
            last_date, last_time = entries[-1]

            # Formato "YYYY-MM-DD HH:MM"
            date_start = f"{first_date} {first_time}" if first_time else first_date
            date_end = f"{last_date} {last_time or first_time}" if last_date != first_date else date_start

            result["date_start"] = date_start
            result["date_end"] = date_end

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
        Estrae la descrizione dell'evento come HTML grezzo da div.spettacolo-content.

        Returns:
            HTML grezzo del blocco descrizione, o None se assente
        """
        html = response.css("div.spettacolo-content").get()
        return html if html else None

    def _extract_costi_info(self, response) -> Optional[str]:
        """
        Estrae il blocco completo "COSTI E INFO" da div.event_costi come HTML grezzo.

        Returns:
            HTML grezzo del blocco costi/info o None
        """
        return response.css("div.event_costi").get()

    # Domini da escludere nella ricerca del sito web esterno
    _EXCLUDED_DOMAINS = (
        "iubenda.com", "facebook.com", "instagram.com", "youtube.com",
        "twitter.com", "x.com", "linkedin.com", "google.com",
        "teatropubblicopugliese.it", "whatsapp.com", "tiktok.com",
    )

    def _is_excluded_url(self, url: str) -> bool:
        """Restituisce True se l'URL appartiene a un dominio da escludere."""
        return any(domain in url for domain in self._EXCLUDED_DOMAINS)

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
