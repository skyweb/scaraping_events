# -*- coding: utf-8 -*-
"""
Spider per suedtirol.info - Portale turistico dell'Alto Adige / Südtirol.

Il sito usa Adobe AEM con Algolia. Le card eventi sono SSR e le pagine
dettaglio hanno JSON-LD Event.

Utilizzo:
    scrapy crawl suedtirol
    scrapy crawl suedtirol -a max_pages=5
"""

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class SuedtirolSpider(BaseEventSpider):
    name = "suedtirol"
    source_name = "suedtirol"
    allowed_domains = ["www.suedtirol.info"]

    BASE_URL = "https://www.suedtirol.info"
    LISTING_URL = f"{BASE_URL}/it/it/esperienze-eventi/eventi-alto-adige"

    custom_settings = {**DEFAULT_CRAWL_SETTINGS}

    def __init__(self, max_pages: str = "5", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self._seen_urls: set[str] = set()

    def start_requests(self):
        yield scrapy.Request(self.LISTING_URL, callback=self._parse_listing, meta={"page": 1})

    def _parse_listing(self, response):
        cards = response.css("article.event-wrapper.js__plp-card-wrapper")
        new_count = 0
        for card in cards:
            href = card.attrib.get("data-href", "")
            if not href:
                continue
            full_url = response.urljoin(href)
            if full_url in self._seen_urls:
                continue
            self._seen_urls.add(full_url)
            new_count += 1
            yield scrapy.Request(full_url, callback=self._parse_detail)

        page = response.meta["page"]
        self.logger.info(f"Pagina {page}: {new_count} nuovi eventi (SSR)")

    def _parse_detail(self, response):
        ld_event = self.extract_jsonld_node(response, "Event") or {}

        title = self.clean_text(ld_event.get("name")) or self.clean_text(response.css("h1.title::text").get())
        if not title:
            return

        description = self.clean_text(ld_event.get("description"))
        if not description:
            description = self.clean_text(response.css("div.sdt-intro .cmp-text p").xpath("string()").get())

        date_start = self.parse_date_iso(ld_event.get("startDate", ""))
        date_end = self.parse_date_iso(ld_event.get("endDate", ""))

        location = ld_event.get("location") or {}
        if isinstance(location, list):
            location = location[0] if location else {}
        address_obj = location.get("address") or {}
        city = self.clean_text(address_obj.get("addressLocality"))
        if not city:
            city = self.clean_text(response.css("div.sdt-city::text").get())

        image_url = ld_event.get("image")
        if isinstance(image_url, list):
            image_url = image_url[0] if image_url else None
        if not image_url:
            image_url = response.xpath('//meta[@property="og:image"]/@content').get()

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
