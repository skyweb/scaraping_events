# -*- coding: utf-8 -*-
"""
Spider per lamialiguria.it - Portale turistico eventi della Liguria.

Il sito è un WordPress con plugin eventi personalizzato.
Il JSON-LD è di tipo WebPage (non Event), quindi i dati strutturati
vengono integrati con HTML parsing dedicato.

Utilizzo:
    # Scrapy diretto - prime N pagine (default: 5)
    scrapy crawl la_mia_liguria -o output.json

    # Con limite pagine
    scrapy crawl la_mia_liguria -a max_pages=10 -o output.json

    # Scrapyd
    curl http://localhost:6800/schedule.json \
        -d project=events_scraper \
        -d spider=la_mia_liguria \
        -d max_pages=10

Parametri:
    max_pages: Numero massimo di pagine listing da scansionare (default: 5)
"""

import json
import re
from typing import Optional

import scrapy

from spiders.base import BaseEventSpider


class LaMiaLiguriaSpider(BaseEventSpider):
    """
    Spider per lamialiguria.it.

    Strategia:
    1. Scorre le pagine lista eventi (/vivi-la-liguria/liguria-eventi/page/N/)
    2. Dalla card estrae URL dettaglio e categoria
    3. Dal dettaglio parsa JSON-LD WebPage (titolo, descrizione, immagine)
    4. Integra date, città e contatti dall'HTML
    """

    name = "la_mia_liguria"
    source_name = "la_mia_liguria"
    allowed_domains = ["lamialiguria.it"]

    BASE_URL = "https://lamialiguria.it"
    EVENTS_URL = "https://lamialiguria.it/vivi-la-liguria/liguria-eventi/"

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
            max_pages: Numero massimo di pagine listing (default: 5)
        """
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self._seen_urls: set = set()

    def start_requests(self):
        """Genera la prima richiesta alla pagina lista eventi."""
        yield scrapy.Request(
            self.EVENTS_URL,
            callback=self.parse,
            meta={"page": 1},
        )

    def parse(self, response):
        """
        Parsa la pagina lista eventi ed estrae URL dettaglio e categoria.
        Paginazione WordPress tramite /page/N/.

        Args:
            response: Risposta HTTP della pagina lista
        """
        # Link agli eventi (pattern /eventi/[slug]/)
        event_links = response.css('a[href*="/eventi/"]')

        new_items = []
        for link in event_links:
            href = link.attrib.get("href", "")
            if not href or href.rstrip("/").endswith("/eventi"):
                continue
            full_url = response.urljoin(href)
            if full_url in self._seen_urls:
                continue
            self._seen_urls.add(full_url)

            # Categoria dalla card (span.underline)
            category_text = self.clean_text(link.css("span.underline::text").get())
            new_items.append((full_url, category_text))

        if not new_items:
            self.logger.info(f"Nessun evento trovato a pagina {response.meta.get('page', 1)}, stop.")
            return

        for url, category_text in new_items:
            yield scrapy.Request(
                url,
                callback=self.parse_event_detail,
                meta={"category_from_list": category_text},
            )

        # Paginazione WordPress: /page/N/
        current_page = response.meta.get("page", 1)
        if current_page < self.max_pages:
            next_page = current_page + 1
            next_url = f"{self.EVENTS_URL}page/{next_page}/"
            yield scrapy.Request(
                next_url,
                callback=self.parse,
                meta={"page": next_page},
            )

    def parse_event_detail(self, response):
        """
        Parsa la pagina di dettaglio evento.
        Fonte primaria: JSON-LD WebPage (titolo, descrizione, immagine).
        Integrazioni HTML: date, città, contatti.

        Args:
            response: Risposta HTTP della pagina dettaglio
        """
        # ── JSON-LD WebPage ───────────────────────────────────────────────────
        ld_page = self._extract_jsonld_webpage(response)

        # Titolo: JSON-LD name → h1 → og:title
        title = (
            (ld_page.get("name") if ld_page else None)
            or self.clean_text(response.css("h1::text").get())
            or response.xpath('//meta[@property="og:title"]/@content').get()
        )
        title = self.clean_text(title)

        # Descrizione: JSON-LD description → og:description
        description = (
            (ld_page.get("description") if ld_page else None)
            or response.xpath('//meta[@property="og:description"]/@content').get()
        )
        description = self.clean_text(description)

        # Immagine: JSON-LD image → og:image
        image_url = (
            (ld_page.get("image") if ld_page else None)
            or response.xpath('//meta[@property="og:image"]/@content').get()
        )

        # ── Quando (date) ─────────────────────────────────────────────────────
        quando = self._extract_quando(response)
        date_start = quando.get("date_start")
        date_end = quando.get("date_end")
        date_display = quando.get("display")

        # ── Dove (città) ─────────────────────────────────────────────────────
        city = self._extract_city(response)

        # ── Contatti ─────────────────────────────────────────────────────────
        contatti = self._extract_contatti(response)
        website = contatti.get("website")

        # ── Categoria ────────────────────────────────────────────────────────
        # Fonte primaria: passata dalla lista; fallback HTML
        cat_from_list = response.meta.get("category_from_list")
        category_html = self._extract_category(response)
        category_value = cat_from_list or (category_html[0] if category_html else None)
        category = [category_value] if category_value else []

        # Slug ed event_id dall'URL
        slug = response.url.rstrip("/").split("/")[-1]

        # Costruzione item
        item = self.create_item(
            url=response.url,
            title=title,
            description=description,
            date_start=date_start,
            date_end=date_end,
            date_display=date_display,
            city=city,
            image_url=image_url,
            category=category,
            website=website,
            slug=slug,
            event_id=slug,
            raw_data={"jsonld": ld_page, "contatti": contatti},
        )

        item["uuid"] = self.generate_uuid(
            item.get("title", ""),
            item.get("date_start", ""),
            item.get("city", ""),
        )
        item["content_hash"] = self.generate_content_hash(
            item.get("description", ""),
            "",
            "",
        )

        self.log_stats(item.get("city"))
        yield item

    # =========================================================================
    # METODI ESTRAZIONE JSON-LD
    # =========================================================================

    def _extract_jsonld_webpage(self, response) -> Optional[dict]:
        """
        Estrae il nodo WebPage dal JSON-LD della pagina.

        Returns:
            Dizionario con i dati della pagina o None
        """
        for script_text in response.css('script[type="application/ld+json"]::text').getall():
            try:
                data = json.loads(script_text)
            except (json.JSONDecodeError, ValueError):
                continue

            # Formato @graph
            if isinstance(data, dict) and "@graph" in data:
                for node in data["@graph"]:
                    if isinstance(node, dict) and node.get("@type") == "WebPage":
                        return node

            # Formato diretto
            if isinstance(data, dict) and data.get("@type") == "WebPage":
                return data

        return None

    # =========================================================================
    # METODI ESTRAZIONE HTML
    # =========================================================================

    def _extract_quando(self, response) -> dict:
        """
        Estrae le date dell'evento dall'HTML.

        Formati gestiti:
        - .data-inizio / .data-fine: "DD/MM/YYYY"
        - .event-date p: "DD/MM/YYYY - DD/MM/YYYY"
        - .evento-meta: contenitore generale

        Returns:
            Dict con: display, date_start, date_end (YYYY-MM-DD)
        """
        quando = {"display": None, "date_start": None, "date_end": None}

        # Formato 1: span.data-inizio / span.data-fine (plugin eventi)
        start_raw = self.clean_text(response.css(".data-inizio::text").get())
        end_raw = self.clean_text(response.css(".data-fine::text").get())
        if start_raw:
            quando["date_start"] = self.parse_date_dmy(start_raw)
            quando["display"] = start_raw
        if end_raw:
            quando["date_end"] = self.parse_date_dmy(end_raw)
            if quando["display"]:
                quando["display"] += f" - {end_raw}"

        # Formato 2: .event-date p → "DD/MM/YYYY - DD/MM/YYYY"
        if not quando["date_start"]:
            date_text = self.clean_text(response.css(".event-date p::text").get())
            if date_text:
                quando["display"] = date_text
                dates = self.extract_dates_from_text(date_text)
                if dates:
                    quando["date_start"] = dates[0]
                if len(dates) >= 2:
                    quando["date_end"] = dates[1]

        # Formato 3: qualsiasi testo con pattern DD/MM/YYYY nell'area meta
        if not quando["date_start"]:
            meta_text = self.clean_text(
                response.css(".evento-meta").xpath("string()").get()
                or response.css(".event-info").xpath("string()").get()
            )
            if meta_text:
                dates = self.extract_dates_from_text(meta_text)
                if dates:
                    quando["date_start"] = dates[0]
                    quando["display"] = meta_text
                if len(dates) >= 2:
                    quando["date_end"] = dates[1]

        # Se date_end == date_start non ha senso tenerlo
        if quando["date_end"] == quando["date_start"]:
            quando["date_end"] = None

        return quando

    def _extract_city(self, response) -> Optional[str]:
        """
        Estrae la città dell'evento dall'HTML.

        Cerca in ordine:
        1. .event-location h5 (campo dedicato)
        2. .evento-location, .luogo (classi alternative)
        3. og:region o altri meta

        Returns:
            Nome città o None
        """
        # Tentativo 1: campo location dedicato
        city = (
            self.clean_text(response.css(".event-location h5::text").get())
            or self.clean_text(response.css(".event-location p::text").get())
            or self.clean_text(response.css(".evento-location::text").get())
            or self.clean_text(response.css(".luogo::text").get())
        )
        if city:
            return city.title()

        # Tentativo 2: meta geo.region o article:region
        region = response.xpath('//meta[@name="geo.region"]/@content').get()
        if region:
            return self.clean_text(region)

        return None

    def _extract_contatti(self, response) -> dict:
        """
        Estrae i contatti dell'evento dall'HTML WordPress.

        Returns:
            Dict con: raw, phone, website
        """
        contatti = {"raw": None, "phone": None, "website": None}

        # Cerca sezione contatti
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
                phone_match = re.search(r"\b[\d][\d\s.\-/]{5,14}[\d]\b", raw)
                if phone_match:
                    contatti["phone"] = phone_match.group(0).strip()

        return contatti

    def _extract_category(self, response) -> list:
        """
        Estrae la categoria dall'HTML WordPress.

        Returns:
            Lista di categorie (può essere vuota)
        """
        cat = (
            self.clean_text(response.css(".cat-links a::text").get())
            or self.clean_text(response.css(".entry-category a::text").get())
            or self.clean_text(response.css(".mec-event-category::text").get())
        )
        return [cat] if cat else []
