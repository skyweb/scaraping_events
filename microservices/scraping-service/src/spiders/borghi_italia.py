# -*- coding: utf-8 -*-
"""
Spider per borghipiubelliditalia.it - Eventi nei borghi italiani.

WordPress + EventON plugin. Usa la WP REST API per la lista eventi
e visita ogni pagina dettaglio per estrarre date, location e regione
dai microdati schema.org (itemprop).

Utilizzo:
    scrapy crawl borghi_italia
    scrapy crawl borghi_italia -a max_pages=3
"""

import re

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class BorghiItaliaSpider(BaseEventSpider):
    """
    Spider per borghipiubelliditalia.it.

    Flusso:
    1. Scarica lista eventi dalla WP REST API con paginazione
    2. Per ogni evento, visita la pagina dettaglio
    3. Estrae date/location dai microdati schema.org (itemprop)
    """

    name = "borghi_italia"
    source_name = "borghi_italia"
    allowed_domains = ["borghipiubelliditalia.it"]

    BASE_URL = "https://borghipiubelliditalia.it"
    API_URL = f"{BASE_URL}/wp-json/wp/v2/ajde_events"

    custom_settings = {**DEFAULT_CRAWL_SETTINGS}

    def __init__(self, max_pages: str = None, per_page: int = 100, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.per_page = min(int(per_page), 100)
        self.max_pages = int(max_pages) if max_pages else None

    def start_requests(self):
        yield scrapy.Request(
            f"{self.API_URL}?per_page={self.per_page}&page=1",
            callback=self.parse,
        )

    def parse(self, response):
        """Parsa lista eventi dalla WP REST API."""
        events_list = response.json()
        total_pages = int(response.headers.get("X-WP-TotalPages", b"1").decode())

        page_match = re.search(r"[?&]page=(\d+)", response.url)
        current_page = int(page_match.group(1)) if page_match else 1

        self.logger.info(f"Pagina {current_page}/{total_pages} — {len(events_list)} eventi")

        for event_data in events_list:
            url = event_data.get("link")
            if not url:
                continue

            title_obj = event_data.get("title", {})
            title = self.clean_html(title_obj.get("rendered", ""))

            # Descrizione dal campo content dell'API
            content_obj = event_data.get("content", {})
            description = content_obj.get("rendered", "")

            yield response.follow(
                url,
                callback=self._parse_detail,
                meta={
                    "api_title": title,
                    "api_description": description,
                },
            )

        # Paginazione
        max_pages = self.max_pages or total_pages
        if current_page < min(max_pages, total_pages):
            next_page = current_page + 1
            yield scrapy.Request(
                f"{self.API_URL}?per_page={self.per_page}&page={next_page}",
                callback=self.parse,
            )

    def _parse_detail(self, response):
        """Estrae dettagli dalla pagina evento usando microdati schema.org."""
        title = response.meta["api_title"]
        description = response.meta["api_description"]

        if not title:
            title = self.clean_text(
                response.css("h1.evosin_event_title::text").get()
            )
        if not title:
            return

        # ── Date dai microdati ────────────────────────────────────────────
        date_start = self._parse_itemprop_date(
            response.css('[itemprop="startDate"]::attr(content)').get()
        )
        date_end = self._parse_itemprop_date(
            response.css('[itemprop="endDate"]::attr(content)').get()
        )
        if date_end == date_start:
            date_end = None

        # Orari dal testo visibile nella sezione Orario
        time_start = None
        time_end = None
        time_els = response.css('[itemprop="startDate"]::attr(content)').get()
        if time_els:
            tm = re.search(r"T(\d{1,2}:\d{2})", time_els)
            if tm:
                time_start = tm.group(1)
        time_end_el = response.css('[itemprop="endDate"]::attr(content)').get()
        if time_end_el:
            tm = re.search(r"T(\d{1,2}:\d{2})", time_end_el)
            if tm:
                time_end = tm.group(1)

        orari = None
        if time_start and time_end:
            orari = f"{time_start} - {time_end}"
        elif time_start:
            orari = time_start

        # ── Location dai microdati ────────────────────────────────────────
        # Il primo itemprop="name" dentro location è il nome del borgo,
        # itemprop="streetAddress" è l'indirizzo
        location_el = response.css('[itemtype*="Place"], [itemprop="location"]')
        location_name = None
        location_address = None
        if location_el:
            location_name = self.clean_text(
                location_el.css('[itemprop="name"]::text').get()
                or location_el.css('[itemprop="name"]::attr(content)').get()
            )
            location_address = self.clean_text(
                location_el.css('[itemprop="streetAddress"]::text').get()
                or location_el.css('[itemprop="streetAddress"]::attr(content)').get()
            )

        # Fallback: dal link nella sezione Posizione
        if not location_name:
            location_name = self.clean_text(
                response.css('.evo_h3.evodfx + * a::text').get()
            )

        # ── Regione dalla classe CSS del post div ─────────────────────────
        region = None
        post_div = response.css('[class*="event_type-"]')
        if post_div:
            classes = post_div.attrib.get("class", "")
            match = re.search(r"event_type-([\w-]+)", classes)
            if match:
                region = match.group(1).replace("-", " ").title()

        # ── Immagine ──────────────────────────────────────────────────────
        image_url = response.css('[itemprop="image"]::attr(content)').get()
        if not image_url:
            image_url = response.xpath('//meta[@property="og:image"]/@content').get()

        # ── Date display ──────────────────────────────────────────────────
        date_display = ""
        date_texts = response.css('.evo_h3:contains("Orario") ~ *::text').getall()
        if date_texts:
            date_display = " ".join(t.strip() for t in date_texts if t.strip())

        # ── Descrizione: preferisci API, fallback pagina ──────────────────
        if not description or description.strip() == "":
            description = response.css('.eventon_desc_in').xpath("string()").get()
            if description:
                description = self.clean_text(description)

        # ── Hash e Item ───────────────────────────────────────────────────
        uuid = self.generate_uuid(title, date_start or "", location_name or "")
        content_hash = self.generate_content_hash(description or "", "", orari or "")

        yield self.create_item(
            uuid=uuid,
            title=title,
            data={
                "description": description,
                "category": ["evento"],
                "image_url": image_url,
                "dates": {
                    "date_start": date_start or "",
                    "date_end": date_end or "",
                    "date_display": date_display,
                },
                "city": {
                    "city_name": location_name,
                    "location_name": location_name,
                    "location_address": location_address,
                    "region": region,
                },
                "section": {
                    "orari": orari,
                },
            },
            meta={
                "content_hash": content_hash,
                "url": response.url,
                "category": "evento",
                "source": self.source_name,
            },
        )

    @staticmethod
    def _parse_itemprop_date(value: str | None) -> str | None:
        """Estrae YYYY-MM-DD da un valore itemprop datetime (es. '2026-3-15T00:00+1:00')."""
        if not value:
            return None
        match = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", value)
        if not match:
            return None
        year, month, day = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
