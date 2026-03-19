# -*- coding: utf-8 -*-
"""
Spider per feelflorence.it - Portale turistico di Firenze e Toscana.

Il sito usa Drupal 10 con tema custom. Lo spider usa la paginazione standard
?page=N e scrapa le pagine dettaglio per i dati completi.

Utilizzo:
    scrapy crawl feel_florence
    scrapy crawl feel_florence -a max_pages=10

Parametri:
    max_pages: Numero massimo di pagine listing da scansionare (default: 5)
"""

import re
from typing import Optional

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class FeelFlorenceSpider(BaseEventSpider):
    """
    Spider per feelflorence.it (Drupal 10).

    Strategia:
    1. Listing paginato via ?page=N (0-indexed, ~10 eventi/pagina)
    2. Per ogni card, segue il link alla pagina dettaglio
    3. Dal dettaglio estrae date (appointments), location (POI), descrizione, immagine
    """

    name = "feel_florence"
    source_name = "feel_florence"
    allowed_domains = ["www.feelflorence.it"]

    LISTING_URL = "https://www.feelflorence.it/it/eventi"

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
        cards = response.css("article.list-teaser")
        new_count = 0

        for card in cards:
            # Il primo <a> figlio diretto contiene il link al dettaglio
            href = card.css("a::attr(href)").get()
            if not href:
                href = card.css("h3.list-teaser-title a::attr(href)").get()
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

        # Paginazione
        has_next = response.css("li.pager__item--next a::attr(href)").get()
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
        title = self.clean_text(response.css("h1::text").get())
        if not title:
            title = self.clean_text(
                response.xpath('//meta[@property="og:title"]/@content').get()
            )
        if not title:
            return

        # Descrizione
        description = self.clean_text(
            response.css(".field--name-field-description .ec-content").xpath("string()").get()
        )
        if not description:
            description = self.clean_text(
                response.xpath('//meta[@property="og:description"]/@content').get()
            )

        # Immagine (og:image ha la migliore qualità)
        image_url = response.xpath('//meta[@property="og:image:url"]/@content').get()
        if not image_url:
            image_url = response.css(".field--name-field-header-media picture img::attr(src)").get()

        # Sottocategoria
        categories = []
        for cat_el in response.css(".field--name-field-subcategories .field__item"):
            cat = self.clean_text(cat_el.xpath("string()").get())
            if cat:
                categories.append(cat)

        # Comune
        city = self.clean_text(
            response.css(".field--name-field-municipalities .field__item::text").get()
        )

        # Appointment: date, orari, prezzi, luogo
        appointment = self._extract_appointment(response)
        date_start = appointment.get("date_start")
        date_end = appointment.get("date_end")
        date_display = appointment.get("date_display", "")
        price = appointment.get("price")
        location_name = appointment.get("location_name")

        if date_end == date_start:
            date_end = None

        # Contatti
        website = response.css(".field--name-field-links a::attr(href)").get()
        phone = self.clean_text(
            response.css(".field--name-field-phones a::text").get()
        )
        email = self.clean_text(
            response.css(".field--name-field-emails a::text").get()
        )

        # Slug

        # Hash
        uuid = self.generate_uuid(title, date_start or "", location_name or city or "Firenze")
        content_hash = self.generate_content_hash(description or "", price or "", "")

        item = self.create_item(
            uuid=uuid,
            title=title,
            data={
                "description": description,
                "category": categories,
                "image_url": image_url,
                "dates": {
                    "date_start": date_start or "",
                    "date_end": date_end or "",
                    "date_display": date_display,
                },
                "city": {
                    "city_name": city or "Firenze",
                    "location_name": location_name,
                    "location_address": None,
                },
                "section": {
                    "price": price,
                    "website": website,
                    "phone": phone,
                    "email": email,
                },
            },
            meta={
                "content_hash": content_hash,
                "url": response.url,
                "event_id": slug,
                "category": categories[0] if categories else "evento",
                "source": self.source_name,
            },
        )

        yield item

    def _extract_appointment(self, response) -> dict:
        """Estrae date, prezzi e luogo dalla sezione appointments."""
        result = {
            "date_start": None,
            "date_end": None,
            "date_display": "",
            "price": None,
            "location_name": None,
        }

        # Sezione appointments
        appointments = response.css(".field--name-field-appointments-revision")
        if not appointments:
            return result

        # Date dalla season-header (formato DD/MM/YYYY - DD/MM/YYYY)
        season_text = self.clean_text(
            appointments.css(".field--name-field-opening-hours .season-header div").xpath("string()").get()
        )
        if season_text:
            result["date_display"] = season_text
            dates = re.findall(r"(\d{2}/\d{2}/\d{4})", season_text)
            if dates:
                result["date_start"] = self.parse_date_dmy(dates[0])
            if len(dates) >= 2:
                result["date_end"] = self.parse_date_dmy(dates[1])

        # Prezzi
        prices = []
        for price_el in appointments.css(".paragraph--type--prices"):
            label = self.clean_text(
                price_el.css(".field--name-field-long-description").xpath("string()").get()
            )
            amount = self.clean_text(
                price_el.css(".field--name-field-price").xpath("string()").get()
            )
            if label and amount:
                prices.append(f"{label}: {amount}")
            elif amount:
                prices.append(amount)
        if prices:
            result["price"] = " | ".join(prices)

        # Luogo (POI linkato)
        poi_name = self.clean_text(
            appointments.css(".field--name-field-pois a::text").get()
        )
        if poi_name:
            result["location_name"] = poi_name

        return result
