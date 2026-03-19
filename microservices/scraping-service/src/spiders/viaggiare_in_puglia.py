# -*- coding: utf-8 -*-
"""
Spider per viaggiareinpuglia.it - Portale turistico della Puglia.

Il sito è un Angular SPA senza API pubblica documentata.
Lo spider scrapa i meta tag OG e i contenuti server-rendered disponibili.

Utilizzo:
    scrapy crawl viaggiare_in_puglia
    scrapy crawl viaggiare_in_puglia -a max_pages=5

Nota: questo sito è un Angular SPA — lo spider potrebbe catturare solo
i contenuti pre-renderizzati (SSR). Per risultati completi potrebbe servire
un browser headless (Splash/Playwright).
"""

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class ViaggiareInPugliaSpider(BaseEventSpider):
    name = "viaggiare_in_puglia"
    source_name = "viaggiare_in_puglia"
    allowed_domains = ["viaggiareinpuglia.it"]

    BASE_URL = "https://viaggiareinpuglia.it"
    LISTING_URL = f"{BASE_URL}/it/eventi"

    custom_settings = {
        **DEFAULT_CRAWL_SETTINGS,
        "DOWNLOAD_DELAY": 2.0,
    }

    def __init__(self, max_pages: str = "5", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self._seen_urls: set[str] = set()

    def start_requests(self):
        yield scrapy.Request(self.LISTING_URL, callback=self._parse_listing)

    def _parse_listing(self, response):
        # Angular SPA: prova a estrarre link da qualsiasi contenuto SSR
        links = response.css('a[href*="/it/eventi/"]::attr(href)').getall()
        links += response.css('a[href*="/evento/"]::attr(href)').getall()
        new_count = 0
        for href in links:
            full_url = response.urljoin(href)
            if full_url in self._seen_urls:
                continue
            self._seen_urls.add(full_url)
            new_count += 1
            yield scrapy.Request(full_url, callback=self._parse_detail)

        self.logger.info(f"Trovati {new_count} link eventi (SSR)")

    def _parse_detail(self, response):
        title = self.clean_text(response.xpath('//meta[@property="og:title"]/@content').get())
        if not title:
            title = self.clean_text(response.css("h1::text").get())
        if not title:
            return

        description = self.clean_text(response.xpath('//meta[@property="og:description"]/@content').get())
        image_url = response.xpath('//meta[@property="og:image"]/@content').get()

        uuid = self.generate_uuid(title, "", "Puglia")
        content_hash = self.generate_content_hash(description or "", "", "")

        yield self.create_item(
            uuid=uuid, title=title,
            data={
                "description": description, "category": [], "image_url": image_url,
                "dates": {"date_start": "", "date_end": "", "date_display": ""},
                "city": {"city_name": None, "location_name": None, "location_address": None},
                "section": {},
            },
        )
