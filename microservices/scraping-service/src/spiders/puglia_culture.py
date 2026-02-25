# -*- coding: utf-8 -*-
"""
Spider per pugliaculture.it - Portale eventi culturali della Puglia.

Il sito usa WordPress con Elementor come page builder.
Il contenuto strutturato (date, luogo, prezzo, cast) è nei blocchi

Strategia:
- WP REST API (/wp-json/wp/v2/evento) per il listing con paginazione nativa
- HTML scraping della pagina dettaglio per estrarre:
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

API_URL = "https://www.pugliaculture.it/wp-json/wp/v2/evento"


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
        # Se non c'è una date_end distinta, è uguale a date_start
        date_end = date_info.get("date_end") or date_start
        date_display = date_info.get("display")
        time_start = date_info.get("time_start")

        # ── Luogo (Teatro) ────────────────────────────────────────────────────
        location_name = self._extract_location(response)

        # ── City name: parte dopo " - " in location_name ──────────────────────
        # es: "Teatro Comunale di Nardò - Nardò" → "Nardò"
        city_name = None
        if location_name and " - " in location_name:
            city_name = location_name.rsplit(" - ", 1)[-1].strip() or None
            # cancella city_name da location_name

        # ── Descrizione (HTML grezzo da div.spettacolo-content) ───────────────
        description = self._extract_description(response)

        # ── COSTI E INFO (blocco completo) ────────────────────────────────────
        costi_info = self._extract_costi_info(response)
        price = self._extract_price_from_costi(costi_info)
        website = self._extract_website_from_costi(response)

        # ── Time info (HTML raw del blocco date) ──────────────────────────────
        time_info = response.css("div.event-dates").get() or None

        # ── Section annidato ────────────────────
        section = {}
        if category:
            section_key = category[0]
            section_data = {}
            # Rassegna = seconda categoria (es: "La Scena dei Ragazzi")
            if len(category) > 1:
                section_data["rassegna"] = category[1]
            # Cast = HTML grezzo del blocco cast/regia
            cast_html = response.css("div.event_cast").get()
            if cast_html:
                section_data["cast"] = cast_html
            elif description:
                section_data["cast"] = description
            section[section_key] = section_data

        # ── Info extra (costi + contatti) ─────────────────────────────────────
        info_extra = {}
        if costi_info:
            info_extra["info_e_costi"] = costi_info
        if website:
            info_extra["info_e_contatti"] = website

        slug = response.meta.get("slug") or self.slug_from_url(response.url)

        item = self.create_item(
            url=response.url,
            title=title,
            description=description,
            date_start=date_start,
            date_end=date_end,
            date_display=date_display,
            time_start=time_start,
            city=city_name,
            location_name=location_name,
            image_url=image_url,
            category=category,
            price=price,
            website=website,
            section=section or None,
            info_extra=info_extra or None,
            time_info=time_info,
            slug=slug,
            event_id=response.meta.get("event_id", slug),
            raw_data={},
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
            <li class="single_data">
              <div class="giorno_esteso">04<br>febbraio</div>
              <div class="data_event_single">
                mercoledì 04 febbraio 2026
                <strong>H: 10:00</strong>
              </div>
            </li>

        Prende la prima data come date_start e l'ultima come date_end.

        Returns:
            Dict con: date_start, date_end (YYYY-MM-DD), time_start (HH:MM), display
        """
        result = {"date_start": None, "date_end": None, "time_start": None, "display": None}

        parsed_dates = []
        first_time = None

        for li in response.css("li.single_data"):
            # Testo data: "mercoledì 04 febbraio 2026"
            date_text = self.clean_text(
                li.css("div.data_event_single::text").get() or ""
            )
            # Orario: "H: 10:00"
            time_text = self.clean_text(
                li.css("div.data_event_single strong::text").get() or ""
            )

            combined = f"{date_text} {time_text}".strip()
            if not any(m in combined.lower() for m in MESI_IT):
                continue

            parsed_date, parsed_time = parse_italian_date_time(combined)
            if not parsed_date:
                continue

            if parsed_date not in parsed_dates:
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
        Estrae la descrizione dell'evento come HTML grezzo da div.spettacolo-content.

        Returns:
            HTML grezzo del blocco descrizione, o None se assente
        """
        html = response.css("div.spettacolo-content").get()
        return html if html else None

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

    # Domini da escludere nella ricerca del sito web esterno
    _EXCLUDED_DOMAINS = (
        "iubenda.com", "facebook.com", "instagram.com", "youtube.com",
        "twitter.com", "x.com", "linkedin.com", "google.com",
        "teatropubblicopugliese.it", "whatsapp.com", "tiktok.com",
    )

    def _extract_website_from_costi(self, response) -> Optional[str]:
        """
        Estrae il sito web esterno di prenotazione/info dal blocco COSTI E INFO,
        escludendo social network e domini di utilità.

        Returns:
            URL del sito esterno (es: vivaticket.com) o None
        """
        # Cerca prima nel blocco event_costi (più probabile contenga link biglietteria)
        for link in response.css("div.event_costi a[href]::attr(href)").getall():
            if link.startswith("http") and not self._is_excluded_url(link):
                return link

        # Fallback: qualsiasi link esterno nella pagina
        for link in response.xpath(
            '//a[starts-with(@href, "http") '
            'and not(contains(@href, "pugliaculture.it"))]/@href'
        ).getall():
            if not self._is_excluded_url(link):
                return link

        return None

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
