# -*- coding: utf-8 -*-
"""
Spider per in-lombardia.it - Portale eventi della Lombardia.

Il sito usa Drupal CMS con structured data JSON-LD (Schema.org Event)
su ogni pagina di dettaglio evento. La categoria e il prezzo vengono
integrati dall'HTML quando non presenti nel JSON-LD.

Utilizzo:
    # Scrapy diretto - prime N pagine (default: 5)
    scrapy crawl in_lombardia -o output.json

    # Con limite pagine
    scrapy crawl in_lombardia -a max_pages=10 -o output.json

    # Scrapyd
    curl http://localhost:6800/schedule.json \
        -d project=events_scraper \
        -d spider=in_lombardia \
        -d max_pages=10

Parametri:
    max_pages: Numero massimo di pagine listing da scansionare (default: 5)
"""

import re
from typing import Optional

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class InLombardiaSpider(BaseEventSpider):
    """
    Spider per in-lombardia.it.

    Strategia:
    1. Scorre le pagine lista eventi (/it/eventi?page=N)
    2. Per ogni card estrae l'URL della pagina di dettaglio
    3. Dal dettaglio parsa il JSON-LD Schema.org Event
    4. Integra categoria e prezzo dall'HTML Drupal
    """

    name = "in_lombardia"
    source_name = "in_lombardia"
    allowed_domains = ["www.in-lombardia.it"]

    BASE_URL = "https://www.in-lombardia.it"
    EVENTS_URL = "https://www.in-lombardia.it/it/eventi"

    custom_settings = {**DEFAULT_CRAWL_SETTINGS}

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
            meta={"page": 0},
        )

    def parse(self, response):
        """
        Parsa la pagina lista eventi ed estrae gli URL delle pagine di dettaglio.
        Gestisce la paginazione tramite ?page=N.

        Args:
            response: Risposta HTTP della pagina lista
        """
        # Estrai tutti i link agli eventi (pattern /it/evento/[slug])
        event_hrefs = response.css('a[href*="/it/evento/"]::attr(href)').getall()

        # Deduplica mantenendo l'ordine
        new_urls = []
        for href in event_hrefs:
            full_url = response.urljoin(href)
            if full_url not in self._seen_urls:
                self._seen_urls.add(full_url)
                new_urls.append(full_url)

        if not new_urls:
            self.logger.info(f"Nessun evento trovato a pagina {response.meta.get('page', 0)}, stop.")
            return

        # Segui ogni URL dettaglio
        for url in new_urls:
            yield scrapy.Request(url, callback=self.parse_event_detail)

        # Paginazione: passa alla pagina successiva se non abbiamo raggiunto il limite
        current_page = response.meta.get("page", 0)
        if current_page < self.max_pages - 1:
            next_page = current_page + 1
            next_url = f"{self.EVENTS_URL}?page={next_page}"
            yield scrapy.Request(
                next_url,
                callback=self.parse,
                meta={"page": next_page},
            )

    def parse_event_detail(self, response):
        """
        Parsa la pagina di dettaglio evento.
        Utilizza il JSON-LD Schema.org come fonte primaria,
        integra categoria, prezzo, quando, dove e contatti dall'HTML.

        Args:
            response: Risposta HTTP della pagina dettaglio
        """
        # Estrai JSON-LD
        ld_event = self.extract_jsonld_node(response, "Event")
        if not ld_event:
            self.logger.warning(f"Nessun JSON-LD Event trovato: {response.url}")
            return

        # Campi dal JSON-LD
        title = self.clean_text(ld_event.get("name"))
        description = self.clean_text(ld_event.get("description"))

        # ── Quando ───────────────────────────────────────────────────────────
        # Fonte primaria: JSON-LD startDate/endDate
        date_start = self.parse_date_iso(ld_event.get("startDate", ""))
        date_end = self.parse_date_iso(ld_event.get("endDate", ""))
        # Fallback HTML "Quando" (es. eventi multi-giorno senza endDate nel JSON-LD)
        quando_html = self._extract_quando_html(response)
        if not date_start and quando_html.get("date_start"):
            date_start = quando_html["date_start"]
        if not date_end and quando_html.get("date_end"):
            date_end = quando_html["date_end"]
        # Se stessa data, non salvare date_end ridondante
        if date_end == date_start:
            date_end = None
        # Data in formato leggibile dall'HTML
        date_display = quando_html.get("display")

        # ── Dove ─────────────────────────────────────────────────────────────
        # Fonte primaria: JSON-LD location
        location = ld_event.get("location") or {}
        location_name = self.clean_text(location.get("name"))
        address_obj = location.get("address") or {}
        location_address = self.clean_text(address_obj.get("streetAddress"))
        city_raw = address_obj.get("addressLocality", "")
        city = city_raw.title() if city_raw else None
        # Fallback HTML "Dove" se JSON-LD incompleto
        if not location_name or not location_address:
            dove_html = self._extract_dove_html(response)
            location_name = location_name or dove_html.get("name")
            location_address = location_address or dove_html.get("address")
            city = city or dove_html.get("city")

        # Coordinate geografiche
        geo = location.get("geo") or {}
        location_coords = None
        if geo.get("latitude") and geo.get("longitude"):
            location_coords = {
                "lat": float(geo["latitude"]),
                "lng": float(geo["longitude"]),
            }

        # Immagine
        image_data = ld_event.get("image") or {}
        if isinstance(image_data, dict):
            image_url = image_data.get("url")
        else:
            image_url = str(image_data) if image_data else None

        # Slug ed event_id dall'URL
        slug = self.slug_from_url(response.url)

        # Campi integrativi dall'HTML
        category = self._extract_category(response)
        price = self._extract_price(response)
        time_start = self._extract_time_start(response)

        # ── Contatti ─────────────────────────────────────────────────────────
        contatti = self._extract_contatti(response)
        website = contatti.get("website")

        # Costruzione item
        item = self.create_item(
            url=response.url,
            title=title,
            description=description,
            date_start=date_start,
            date_end=date_end,
            date_display=date_display,
            location_name=location_name,
            location_address=location_address,
            location_coords=location_coords,
            city=city,
            image_url=image_url,
            category=category,
            price=price,
            time_start=time_start,
            website=website,
            slug=slug,
            event_id=slug,
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

        yield item

    # =========================================================================
    # METODI ESTRAZIONE HTML (integrativi)
    # =========================================================================

    def _extract_quando_html(self, response) -> dict:
        """
        Estrae la sezione "Quando" dall'HTML come fallback/complemento al JSON-LD.
        Utile per eventi multi-giorno dove endDate potrebbe mancare nel JSON-LD.

        Returns:
            Dict con: display (testo grezzo), date_start, date_end (YYYY-MM-DD)
        """
        quando = {"display": None, "date_start": None, "date_end": None}

        # Cerca h5 "Quando" e il testo seguente
        raw_text = response.xpath(
            '//h5[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "quando")]'
            '/following-sibling::text()[normalize-space()][1]'
        ).get()

        if not raw_text:
            raw_text = response.xpath(
                '//h5[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "quando")]'
                '/following-sibling::p[1]/text()'
            ).get()

        raw_text = self.clean_text(raw_text)
        if raw_text:
            quando["display"] = raw_text
            dates = self.extract_dates_from_text(raw_text)
            if dates:
                quando["date_start"] = dates[0]
            if len(dates) >= 2:
                quando["date_end"] = dates[1]

        return quando

    def _extract_dove_html(self, response) -> dict:
        """
        Estrae la sezione "Dove" dall'HTML come fallback al JSON-LD location.
        Parsa il testo grezzo nel formato "NomeVenue\\nIndirizzo, CITTÀ".

        Returns:
            Dict con: name, address, city
        """
        dove = {"name": None, "address": None, "city": None}

        # Cerca h5 "Dove" e raccoglie i nodi testo successivi
        raw_nodes = response.xpath(
            '//h5[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "dove")]'
            '/following-sibling::text()'
        ).getall()

        lines = [self.clean_text(n) for n in raw_nodes if self.clean_text(n)]
        if not lines:
            # Prova a cercare in un p successivo
            raw_p = response.xpath(
                '//h5[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "dove")]'
                '/following-sibling::p[1]'
            ).xpath("string()").get()
            if raw_p:
                lines = [l.strip() for l in raw_p.split("\n") if l.strip()]

        if lines:
            # Prima riga: nome venue
            dove["name"] = lines[0]
            # Seconda riga (se presente): indirizzo, CITTÀ
            if len(lines) > 1:
                address_line = lines[1]
                # Tenta separazione "Via X, N, CITTÀ" → città in maiuscolo alla fine
                parts = address_line.rsplit(",", 1)
                if len(parts) == 2:
                    dove["address"] = self.clean_text(parts[0])
                    city_part = self.clean_text(parts[1])
                    dove["city"] = city_part.title() if city_part else None
                else:
                    dove["address"] = address_line

        return dove

    def _extract_contatti(self, response) -> dict:
        """
        Estrae la sezione "Contatti" dall'HTML.
        Raccoglie telefono, sito web e altre info di contatto.

        Returns:
            Dict con: raw (testo grezzo), phone, website
        """
        contatti = {"raw": None, "phone": None, "website": None}

        # Cerca h5 "Contatti"
        raw_texts = response.xpath(
            '//h5[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "contatti")]'
            '/following-sibling::text()[normalize-space()]'
        ).getall()

        website_href = response.xpath(
            '//h5[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "contatti")]'
            '/following-sibling::a[starts-with(@href, "http")][1]/@href'
        ).get()

        raw_all = " | ".join(self.clean_text(t) for t in raw_texts if self.clean_text(t))
        contatti["raw"] = raw_all if raw_all else None

        if contatti["raw"]:
            contatti["phone"] = self.extract_phone_from_text(contatti["raw"])

        if website_href:
            contatti["website"] = website_href

        return contatti

    def _extract_category(self, response) -> list:
        """
        Estrae la categoria/tipologia dall'HTML Drupal.
        Usa il campo tassonomia field-name-field-temi.

        Returns:
            Lista di categorie (può essere vuota)
        """
        # Tassonomia Drupal: field--name-field-temi (Drupal 8+) o field-name-field-temi (D7)
        cat = (
            response.css(".field--name-field-temi a::text").get()
            or response.css(".field-name-field-temi a::text").get()
            or response.css(".field--name-field-tipologia a::text").get()
        )
        cat = self.clean_text(cat)
        return [cat] if cat else []

    def _extract_price(self, response) -> Optional[str]:
        """
        Estrae il prezzo dall'HTML, cercando l'elemento <p>
        che segue l'intestazione "Biglietti" o "Prezzo".

        Returns:
            Stringa prezzo o None
        """
        # Cerca h4 con testo "Biglietti" e prende il paragrafo successivo
        price_text = response.xpath(
            '//h4[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "biglietti")]'
            '/following-sibling::p[1]/text()'
        ).get()

        if not price_text:
            price_text = response.xpath(
                '//h4[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "prezzo")]'
                '/following-sibling::p[1]/text()'
            ).get()

        if not price_text:
            # Fallback: cerca campo Drupal specifico
            price_text = (
                response.css(".field--name-field-prezzo::text").get()
                or response.css(".field-name-field-prezzo .field-item::text").get()
            )

        return self.clean_text(price_text)

    def _extract_time_start(self, response) -> Optional[str]:
        """
        Estrae l'orario di inizio dall'HTML, cercando il paragrafo
        che segue l'intestazione "Orari".

        Returns:
            Orario in formato HH:MM o None
        """
        time_text = response.xpath(
            '//h4[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "orari")]'
            '/following-sibling::p[1]/text()'
        ).get()
        time_text = self.clean_text(time_text)

        if not time_text:
            return None

        # Valida formato HH:MM
        match = re.match(r"^(\d{1,2}:\d{2})", time_text)
        return match.group(1) if match else time_text
