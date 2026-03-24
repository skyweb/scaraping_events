# -*- coding: utf-8 -*-
"""
Spider per lamialiguria.it - Portale turistico eventi della Liguria.

Approccio ibrido:
- API WordPress REST per listing, titolo, descrizione, immagine, categoria
- HTML scraping per date, città, contatti (non esposti dall'API MEC)

Utilizzo:
    # Scrapy diretto - prime N pagine API (default: 5, 10 eventi/pagina)
    scrapy crawl la_mia_liguria

    # Con limite pagine API
    scrapy crawl la_mia_liguria -a max_pages=10

    # Scrapyd
    curl http://localhost:6800/schedule.json \
        -d project=events_scraper \
        -d spider=la_mia_liguria \
        -d max_pages=10

Parametri:
    max_pages: Numero massimo di pagine API da scansionare (default: 5)
"""

import json
import re
from typing import Optional

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class LaMiaLiguriaSpider(BaseEventSpider):
    """
    Spider ibrido per lamialiguria.it (WordPress + MEC plugin).

    Strategia:
    1. API REST /wp/v2/mec-events per listing paginato (titolo, descrizione, immagine, categoria)
    2. API REST /wp/v2/media/{id} per URL immagine featured
    3. HTML scraping pagina dettaglio per date, città, contatti (non esposti dall'API)
    """

    name = "la_mia_liguria"
    source_name = "la_mia_liguria"
    allowed_domains = ["lamialiguria.it"]

    BASE_URL = "https://lamialiguria.it"
    API_EVENTS = "https://lamialiguria.it/wp-json/wp/v2/mec-events"
    API_MEDIA = "https://lamialiguria.it/wp-json/wp/v2/media"
    API_CATEGORY = "https://lamialiguria.it/wp-json/wp/v2/mec_category"
    API_PER_PAGE = 10

    custom_settings = {**DEFAULT_CRAWL_SETTINGS}

    def __init__(self, max_pages: str = "5", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self._categories_cache: dict[int, str] = {}

    def start_requests(self):
        """Scarica prima le categorie MEC, poi avvia il listing eventi."""
        yield scrapy.Request(
            f"{self.API_CATEGORY}?per_page=100",
            callback=self._parse_categories,
        )

    def _parse_categories(self, response):
        """Cacha le categorie MEC (id → name), poi avvia il listing."""
        try:
            categories = json.loads(response.text)
            for cat in categories:
                self._categories_cache[cat["id"]] = cat.get("name", "")
            self.logger.info(f"Categorie MEC cachate: {len(self._categories_cache)}")
        except (json.JSONDecodeError, KeyError):
            self.logger.warning("Impossibile caricare categorie MEC")

        # Avvia listing eventi dalla pagina 1
        yield scrapy.Request(
            f"{self.API_EVENTS}?per_page={self.API_PER_PAGE}&page=1&orderby=date&order=desc",
            callback=self._parse_api_listing,
            meta={"page": 1},
        )

    def _parse_api_listing(self, response):
        """
        Parsa la risposta API listing eventi.
        Per ogni evento: estrae dati API, poi segue la pagina HTML per date/location.
        """
        try:
            events = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error(f"Risposta API non valida: {response.url}")
            return

        if not events:
            self.logger.info(f"Nessun evento a pagina {response.meta['page']}, stop.")
            return

        for event in events:
            api_data = self._extract_api_data(event)

            # Segui la pagina HTML per date, città, contatti
            yield scrapy.Request(
                api_data["url"],
                callback=self._parse_event_detail,
                meta={"api_data": api_data},
            )

        # Paginazione API
        current_page = response.meta["page"]
        total_pages = int(response.headers.get(b"X-WP-TotalPages", b"1").decode())
        if current_page < min(self.max_pages, total_pages):
            next_page = current_page + 1
            yield scrapy.Request(
                f"{self.API_EVENTS}?per_page={self.API_PER_PAGE}&page={next_page}&orderby=date&order=desc",
                callback=self._parse_api_listing,
                meta={"page": next_page},
            )

    def _extract_api_data(self, event: dict) -> dict:
        """Estrae i dati disponibili dall'API WordPress."""
        # Titolo
        title = self.clean_text(event.get("title", {}).get("rendered", ""))

        # Descrizione dal content (pulita da HTML)
        content_html = event.get("content", {}).get("rendered", "")
        description = self.clean_html(content_html) if content_html else None

        # Immagine: featured_media è un ID, serve risolverlo
        featured_media_id = event.get("featured_media", 0)

        # Categorie MEC (risolvi ID → nome)
        cat_ids = event.get("mec_category", [])
        categories = [
            self._categories_cache[cid]
            for cid in cat_ids
            if cid in self._categories_cache
        ]

        # URL pagina evento
        url = event.get("link", "")
        return {
            "wp_id": event.get("id"),
            "title": title,
            "description": description,
            "description_html": content_html,
            "categories": categories,
            "featured_media_id": featured_media_id,
            "url": url,
        }

    def _parse_event_detail(self, response):
        """
        Parsa la pagina HTML dettaglio evento.
        Combina dati API (titolo, descrizione, categoria) con HTML (date, città, contatti).
        """
        api_data = response.meta["api_data"]

        # ── Immagine: og:image dal HTML (più semplice che chiamare API media) ──
        image_url = response.xpath('//meta[@property="og:image"]/@content').get()

        # ── Date dall'HTML ─────────────────────────────────────────────────────
        quando = self._extract_quando(response)
        date_start = quando.get("date_start")
        date_end = quando.get("date_end")
        date_display = quando.get("display")

        # ── Città dall'HTML ────────────────────────────────────────────────────
        city = self._extract_city(response)
        location_name = self._extract_location_name(response)

        # ── Contatti dall'HTML ─────────────────────────────────────────────────
        contatti = self._extract_contatti(response)

        # Categoria
        categories = api_data["categories"]
        if not categories:
            categories = self._extract_category(response)
        category_value = categories[0] if categories else None

        # Hash
        title = api_data["title"]
        uuid = self.generate_uuid(title or "", date_start or "", city or location_name or "")
        content_hash = self.generate_content_hash(api_data["description"] or "", "", "")

        # Costruzione EventItem
        item = self.create_item(
            uuid=uuid,
            title=title,
            data={
                "description": api_data["description"],
                "category": categories,
                "image_url": image_url,
                "dates": {
                    "date_start": date_start or "",
                    "date_end": date_end or "",
                    "date_display": date_display or "",
                },
                "city": {
                    "city_name": city,
                    "location_name": location_name,
                    "location_address": None,
                },
                "section": {
                    "website": contatti.get("website"),
                    "contatti": contatti.get("raw"),
                    "phone": contatti.get("phone"),
                },
            },
            meta={
                "content_hash": content_hash,
                "url": api_data["url"],
                "category": category_value or "evento",
                "source": self.source_name,
            },
        )

        yield item

    # =========================================================================
    # METODI ESTRAZIONE HTML (date, città, contatti - non disponibili via API)
    # =========================================================================

    def _extract_quando(self, response) -> dict:
        """Estrae date dall'HTML. Plugin MEC usa classi mec-*."""
        quando = {"display": None, "date_start": None, "date_end": None}

        # MEC: .mec-start-date-abbr, .mec-end-date-abbr (attributo content ISO)
        start_abbr = response.css(".mec-start-date-abbr::attr(content)").get()
        end_abbr = response.css(".mec-end-date-abbr::attr(content)").get()
        if start_abbr:
            quando["date_start"] = self.parse_date_iso(start_abbr)
        if end_abbr:
            quando["date_end"] = self.parse_date_iso(end_abbr)

        # MEC: testo visuale date
        date_display = self.clean_text(
            response.css(".mec-single-event-date .mec-events-abbr-date::text").get()
            or response.css(".mec-single-event-date").xpath("string()").get()
        )
        quando["display"] = date_display

        # MEC: orario dall'HTML
        time_text = self.clean_text(
            response.css(".mec-single-event-time .mec-events-abbr-time::text").get()
            or response.css(".mec-single-event-time").xpath("string()").get()
        )
        if time_text and quando["date_start"]:
            times = re.findall(r"(\d{1,2}:\d{2})", time_text)
            if times:
                quando["date_start"] = f"{quando['date_start']} {times[0]}"
                if quando["date_end"] and len(times) >= 2:
                    quando["date_end"] = f"{quando['date_end']} {times[1]}"

        # Fallback: span.data-inizio / span.data-fine
        if not quando["date_start"]:
            start_raw = self.clean_text(response.css(".data-inizio::text").get())
            if start_raw:
                quando["date_start"] = self.parse_date_dmy(start_raw)
                quando["display"] = start_raw

            end_raw = self.clean_text(response.css(".data-fine::text").get())
            if end_raw:
                quando["date_end"] = self.parse_date_dmy(end_raw)
                if quando["display"]:
                    quando["display"] += f" - {end_raw}"

        # Fallback: .event-date p, .evento-meta
        if not quando["date_start"]:
            date_text = self.clean_text(
                response.css(".event-date p::text").get()
                or response.css(".evento-meta").xpath("string()").get()
                or response.css(".event-info").xpath("string()").get()
            )
            if date_text:
                quando["display"] = date_text
                dates = self.extract_dates_from_text(date_text)
                if dates:
                    quando["date_start"] = dates[0]
                if len(dates) >= 2:
                    quando["date_end"] = dates[1]

        # Se stessa data, non salvare date_end ridondante
        if quando["date_end"] == quando["date_start"]:
            quando["date_end"] = None

        return quando

    def _extract_city(self, response) -> Optional[str]:
        """Estrae la città dall'HTML MEC o fallback generico."""
        city = (
            # MEC location
            self.clean_text(response.css(".mec-single-event-location .mec-address::text").get())
            or self.clean_text(response.css(".mec-single-event-location .mec-location-address::text").get())
            # Fallback generico
            or self.clean_text(response.css(".event-location h5::text").get())
            or self.clean_text(response.css(".event-location p::text").get())
            or self.clean_text(response.css(".evento-location::text").get())
            or self.clean_text(response.css(".luogo::text").get())
        )
        if city:
            return city.title()

        # Meta geo.region
        region = response.xpath('//meta[@name="geo.region"]/@content').get()
        if region:
            return self.clean_text(region)

        return None

    def _extract_location_name(self, response) -> Optional[str]:
        """Estrae il nome della venue dall'HTML MEC."""
        return (
            self.clean_text(response.css(".mec-single-event-location .mec-location-title::text").get())
            or self.clean_text(response.css(".mec-single-event-location h6::text").get())
        )

    def _extract_contatti(self, response) -> dict:
        """Estrae contatti dall'HTML."""
        contatti = {"raw": None, "phone": None, "website": None}

        # MEC organizer
        organizer_section = response.css(".mec-single-event-organizer")
        if organizer_section:
            raw = self.clean_text(organizer_section.xpath("string()").get())
            contatti["raw"] = raw

            website = organizer_section.css('a[href^="http"]::attr(href)').get()
            if website and "lamialiguria.it" not in website:
                contatti["website"] = website

            if raw:
                contatti["phone"] = self.extract_phone_from_text(raw)

            return contatti

        # Fallback generico
        contatti_section = (
            response.css(".event-contacts")
            or response.css(".contatti")
            or response.css(".contact-info")
        )

        if contatti_section:
            raw = self.clean_text(contatti_section.xpath("string()").get())
            contatti["raw"] = raw

            website = contatti_section.css('a[href^="http"]::attr(href)').get()
            if website and "lamialiguria.it" not in website:
                contatti["website"] = website

            if raw:
                contatti["phone"] = self.extract_phone_from_text(raw)

        return contatti

    def _extract_category(self, response) -> list:
        """Estrae la categoria dall'HTML come fallback."""
        cat = (
            self.clean_text(response.css(".mec-event-category::text").get())
            or self.clean_text(response.css(".cat-links a::text").get())
            or self.clean_text(response.css(".entry-category a::text").get())
        )
        return [cat] if cat else []
