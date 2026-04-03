# -*- coding: utf-8 -*-
"""
Spider per yesmilano.it - Portale turistico di Milano.

Il sito usa Drupal 10 con Views Infinite Scroll. Lo spider usa la paginazione
standard ?page=N e scrapa le pagine dettaglio per i dati completi.

Utilizzo:
    scrapy crawl yes_milano
    scrapy crawl yes_milano -a max_pages=5

Parametri:
    max_pages: Numero massimo di pagine listing da scansionare (default: 5)
"""

import re
from typing import Optional

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class YesMilanoSpider(BaseEventSpider):
    """
    Spider per yesmilano.it (Drupal 10).

    Strategia:
    1. Listing paginato via ?page=N (0-indexed, ~12 eventi/pagina)
    2. Per ogni card, segue il link alla pagina dettaglio
    3. Dal dettaglio estrae date (<time datetime>), location, descrizione, immagine
    """

    name = "yes_milano"
    source_name = "yes_milano"
    allowed_domains = ["www.yesmilano.it"]

    LISTING_URL = "https://www.yesmilano.it/eventi/tutti-gli-eventi"

    custom_settings = {**DEFAULT_CRAWL_SETTINGS}

    def __init__(self, max_pages: str = "5", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self._seen_urls: set[str] = set()

    def start_requests(self):
        """Avvia dal listing pagina 0."""
        yield scrapy.Request(
            f"{self.LISTING_URL}?page=0",
            callback=self._parse_listing,
            meta={"page": 0},
        )

    def _parse_listing(self, response):
        """Parsa la pagina listing ed estrae i link ai dettagli."""
        cards = response.css("div.event-top-event.card")
        new_count = 0

        for card in cards:
            href = card.css('a[rel="bookmark"]::attr(href)').get()
            if not href:
                continue
            full_url = response.urljoin(href)
            if full_url in self._seen_urls:
                continue
            self._seen_urls.add(full_url)
            new_count += 1

            yield scrapy.Request(full_url, callback=self._parse_detail)

        page = response.meta["page"]
        self.logger.info(f"Pagina {page}: {new_count} nuovi eventi trovati")

        # Paginazione: controlla se c'è un link "next"
        has_next = response.css('li.pager__item--next a::attr(href)').get()
        next_page = page + 1
        if has_next and next_page < self.max_pages:
            yield scrapy.Request(
                f"{self.LISTING_URL}?page={next_page}",
                callback=self._parse_listing,
                meta={"page": next_page},
            )

    def _parse_detail(self, response):
        """Parsa la pagina dettaglio evento."""
        # Titolo
        title = self.clean_text(response.css("h1 span::text").get())
        if not title:
            title = self.clean_text(
                response.xpath('//meta[@property="og:title"]/@content').get()
            )
        if not title:
            return

        # Descrizione
        description = self.clean_text(
            response.css(".field--name-field-descrizione .field--item").xpath("string()").get()
        )
        if not description:
            description = self.clean_text(
                response.xpath('//meta[@property="og:description"]/@content').get()
            )

        # Date da <time datetime="...">
        time_elements = response.css("div.caption_date time[datetime]")
        date_start = None
        date_end = None
        if time_elements:
            dt_start = time_elements[0].attrib.get("datetime", "")
            date_start = self.parse_date_iso(dt_start)
            # Orario
            time_match = re.search(r"T(\d{2}:\d{2})", dt_start)
            if time_match and date_start and time_match.group(1) != "12:00":
                date_start = f"{date_start} {time_match.group(1)}"
        if len(time_elements) >= 2:
            dt_end = time_elements[1].attrib.get("datetime", "")
            date_end = self.parse_date_iso(dt_end)

        date_display = self.clean_text(
            response.css("div.caption_date").xpath("string()").get()
        )

        if date_end == date_start:
            date_end = None

        # Location
        location_name = self.clean_text(
            response.css(".field--name-field-location .field--item::text").get()
        )
        location_address = self.clean_text(
            response.css(".field--name-field-indirizzo").xpath("string()").get()
        )

        # Immagine
        image_url = response.xpath('//meta[@property="og:image"]/@content').get()

        # Contatti
        phone = self.clean_text(
            response.css(".field--name-field-telefono .field--item::text").get()
        )
        email = self.clean_text(
            response.css(".field--name-field-email .field--item::text").get()
        )
        website = response.css(".field--name-field-link a::attr(href)").get()

        # Biglietti
        ticket_info = self.clean_text(
            response.css(".field--name-field-info-biglietto .field--item").xpath("string()").get()
        )
        buy_url = response.css(".field--name-field-acquista-online a::attr(href)").get()

        # Hash
        uuid = self.generate_uuid(title, date_start or "", location_name or "Milano")
        content_hash = self.generate_content_hash(description or "", ticket_info or "", "")

        contacts = [v for v in [phone, email, website, buy_url] if v]

        item = self.create_item(
            uuid=uuid,
            title=title,
            data={
                "description": description,
                "category": [],
                "cover_url": image_url,
                "price": ticket_info,
                "dates": {
                    "date_start": date_start or "",
                    "date_end": date_end or "",
                    "date_display": date_display or "",
                },
                "city": {
                    "city_name": "Milano",
                    "location_name": location_name,
                    "location_address": location_address,
                },
                "contacts": contacts or None,
            },
            meta={
                "content_hash": content_hash,
                "url": response.url,
                "category": "evento",
                "source": self.source_name,
            },
        )

        yield item
