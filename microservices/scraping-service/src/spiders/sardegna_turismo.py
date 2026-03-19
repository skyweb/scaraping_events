# -*- coding: utf-8 -*-
"""
Spider per sardegnaturismo.it - Portale turistico della Sardegna.

Drupal 7 con Views AJAX per paginazione. Date in formato ISO nell'attributo
content degli span.date-display-*.

Utilizzo:
    scrapy crawl sardegna_turismo
    scrapy crawl sardegna_turismo -a max_pages=5
"""

import json

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class SardegnaTurismoSpider(BaseEventSpider):
    name = "sardegna_turismo"
    source_name = "sardegna_turismo"
    allowed_domains = ["www.sardegnaturismo.it"]

    BASE_URL = "https://www.sardegnaturismo.it"
    LISTING_URL = f"{BASE_URL}/it/eventi"
    AJAX_URL = f"{BASE_URL}/it/views/ajax"

    custom_settings = {**DEFAULT_CRAWL_SETTINGS}

    def __init__(self, max_pages: str = "5", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self._seen_urls: set[str] = set()
        self._view_dom_id = ""

    def start_requests(self):
        yield scrapy.Request(self.LISTING_URL, callback=self._parse_initial)

    def _parse_initial(self, response):
        # Estrai view_dom_id per le richieste AJAX successive
        import re
        dom_id_match = re.search(r'"view_dom_id"\s*:\s*"([a-f0-9]+)"', response.text)
        if dom_id_match:
            self._view_dom_id = dom_id_match.group(1)

        # Parsa eventi dalla pagina iniziale
        yield from self._extract_events(response)

        # Richiedi pagina 1 via AJAX
        if self.max_pages > 1:
            yield self._ajax_request(1)

    def _ajax_request(self, page: int):
        return scrapy.FormRequest(
            self.AJAX_URL,
            formdata={
                "view_name": "eventi_da_non_perdere",
                "view_display_id": "page",
                "view_dom_id": self._view_dom_id,
                "pager_element": "0",
                "page": str(page),
            },
            callback=self._parse_ajax,
            meta={"page": page},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    def _parse_ajax(self, response):
        page = response.meta["page"]
        try:
            ajax_data = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error(f"Risposta AJAX non valida pagina {page}")
            return

        html = ""
        for cmd in ajax_data:
            if cmd.get("command") == "insert" and cmd.get("data"):
                html = cmd["data"]
                break

        if not html:
            return

        fake = response.replace(body=html.encode("utf-8"))
        events = list(self._extract_events(fake))
        yield from events

        if events and (page + 1) < self.max_pages:
            yield self._ajax_request(page + 1)

    def _extract_events(self, response):
        cards = response.css("div.node.node-evento")
        new_count = 0
        for card in cards:
            href = card.attrib.get("about") or card.css("a::attr(href)").get()
            if not href:
                continue
            full_url = f"{self.BASE_URL}{href}" if href.startswith("/") else href
            if full_url in self._seen_urls:
                continue
            self._seen_urls.add(full_url)
            new_count += 1
            yield scrapy.Request(full_url, callback=self._parse_detail)

        self.logger.info(f"Estratti {new_count} nuovi eventi")

    def _parse_detail(self, response):
        title = self.clean_text(response.css("h1::text").get())
        if not title:
            return

        description = self.clean_text(
            response.css(".field-name-body .field-item").xpath("string()").get()
        )
        image_url = response.css(".field-name-field-immagine-top img::attr(src)").get()

        # Date ISO dall'attributo content
        date_start = None
        date_end = None
        start_el = response.css("span.date-display-start")
        end_el = response.css("span.date-display-end")
        single_el = response.css("span.date-display-single")

        if start_el:
            date_start = self.parse_date_iso(start_el.attrib.get("content", ""))
        elif single_el:
            date_start = self.parse_date_iso(single_el.attrib.get("content", ""))
        if end_el:
            date_end = self.parse_date_iso(end_el.attrib.get("content", ""))

        # Location dalle tappe
        city = self.clean_text(
            response.css(".field-name-field-riassunto-tappe-nomi .field-item::text").get()
        )

        if date_end == date_start:
            date_end = None

        slug = self.slug_from_url(response.url)
        uuid = self.generate_uuid(title, date_start or "", city or "")
        content_hash = self.generate_content_hash(description or "", "", "")

        yield self.create_item(
            uuid=uuid, title=title,
            data={
                "description": description, "category": [], "image_url": image_url,
                "dates": {"date_start": date_start or "", "date_end": date_end or "", "date_display": ""},
                "city": {"city_name": city, "location_name": None, "location_address": None},
                "section": {},
            },
            meta={"content_hash": content_hash, "url": response.url, "slug": slug, "event_id": slug, "category": "evento", "source": self.source_name},
        )
