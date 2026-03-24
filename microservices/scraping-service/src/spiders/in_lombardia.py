# -*- coding: utf-8 -*-
"""
Spider per in-lombardia.it - Portale eventi della Lombardia.

Il sito usa Drupal CMS con Views AJAX per il listing e JSON-LD Schema.org Event
nelle pagine dettaglio. Lo spider usa l'endpoint AJAX /views/ajax per la paginazione
e poi scrapa le pagine dettaglio per i dati strutturati.

Utilizzo:
    # Scrapy diretto - prime N pagine (default: 5)
    scrapy crawl in_lombardia

    # Con limite pagine
    scrapy crawl in_lombardia -a max_pages=10

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
from urllib.parse import urlencode

import scrapy
from scrapy import Selector

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class InLombardiaSpider(BaseEventSpider):
    """
    Spider per in-lombardia.it (Drupal + Views AJAX).

    Strategia:
    1. Prima richiesta GET alla pagina /eventi per caricare la vista iniziale
    2. Paginazione via POST a /views/ajax con parametri Drupal Views
    3. Per ogni card estrae l'URL della pagina di dettaglio
    4. Dal dettaglio parsa il JSON-LD Schema.org Event + HTML integrativo
    """

    name = "in_lombardia"
    source_name = "in_lombardia"
    allowed_domains = ["www.in-lombardia.it"]

    BASE_URL = "https://www.in-lombardia.it"
    EVENTS_URL = "https://www.in-lombardia.it/eventi"
    VIEWS_AJAX_URL = "https://www.in-lombardia.it/views/ajax"

    # Parametri Drupal Views AJAX
    VIEWS_CONFIG = {
        "view_name": "aggregatore_eventi",
        "view_display_id": "aggregatore",
        "view_args": "24533",
        "view_path": "/node/24533",
    }

    custom_settings = {**DEFAULT_CRAWL_SETTINGS}

    def __init__(self, max_pages: str = "5", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self._seen_urls: set[str] = set()
        self._view_dom_id: str = ""

    def start_requests(self):
        """Prima richiesta GET alla pagina /eventi per estrarre il dom_id e gli eventi iniziali."""
        yield scrapy.Request(
            self.EVENTS_URL,
            callback=self._parse_initial_page,
        )

    def _parse_initial_page(self, response):
        """Parsa la pagina iniziale: estrae dom_id e card eventi."""
        # Estrai view_dom_id dal JS (necessario per le richieste AJAX)
        dom_id_match = re.search(r'"view_dom_id"\s*:\s*"([a-f0-9]+)"', response.text)
        if dom_id_match:
            self._view_dom_id = dom_id_match.group(1)
            self.logger.info(f"view_dom_id: {self._view_dom_id}")

        # Parsa le card dalla pagina iniziale (pagina 0)
        yield from self._extract_event_links(response, page=0)

        # Prosegui con la paginazione AJAX
        if self.max_pages > 1:
            yield from self._request_ajax_page(1)

    def _request_ajax_page(self, page: int):
        """Genera la richiesta AJAX per una pagina specifica."""
        if page >= self.max_pages:
            return

        form_data = {
            "view_name": self.VIEWS_CONFIG["view_name"],
            "view_display_id": self.VIEWS_CONFIG["view_display_id"],
            "view_args": self.VIEWS_CONFIG["view_args"],
            "view_path": self.VIEWS_CONFIG["view_path"],
            "view_dom_id": self._view_dom_id,
            "pager_element": "0",
            "page": str(page),
        }

        yield scrapy.FormRequest(
            self.VIEWS_AJAX_URL,
            formdata=form_data,
            callback=self._parse_ajax_response,
            meta={"page": page},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    def _parse_ajax_response(self, response):
        """Parsa la risposta AJAX di Drupal Views."""
        import json

        page = response.meta["page"]

        try:
            ajax_data = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error(f"Risposta AJAX non valida a pagina {page}")
            return

        # Drupal Views AJAX ritorna una lista di comandi
        html_content = ""
        for command in ajax_data:
            if command.get("command") == "insert" and command.get("data"):
                html_content = command["data"]
                break

        if not html_content:
            self.logger.info(f"Nessun contenuto HTML a pagina {page}, stop.")
            return

        # Parsa l'HTML inserito
        fake_response = response.replace(body=html_content.encode("utf-8"))
        links_found = list(self._extract_event_links(fake_response, page))

        if not links_found:
            self.logger.info(f"Nessun evento a pagina {page}, stop.")
            return

        yield from links_found

        # Pagina successiva
        yield from self._request_ajax_page(page + 1)

    def _extract_event_links(self, response, page: int):
        """Estrae i link alle pagine dettaglio evento dalle card."""
        event_hrefs = response.css('a[href*="/evento/"]::attr(href)').getall()

        new_count = 0
        for href in event_hrefs:
            full_url = response.urljoin(href) if not href.startswith("http") else href
            # Normalizza URL
            if not full_url.startswith("http"):
                full_url = f"{self.BASE_URL}{href}"

            if full_url in self._seen_urls:
                continue
            self._seen_urls.add(full_url)
            new_count += 1

            yield scrapy.Request(full_url, callback=self.parse_event_detail)

        self.logger.info(f"Pagina {page}: {new_count} nuovi eventi trovati")

    def parse_event_detail(self, response):
        """
        Parsa la pagina di dettaglio evento.
        Fonte primaria: JSON-LD Schema.org Event se disponibile, altrimenti HTML.
        """
        # ── JSON-LD Event (opzionale) ──────────────────────────────────────────
        ld_event = self.extract_jsonld_node(response, "Event") or {}

        # ── Titolo ─────────────────────────────────────────────────────────────
        title = self.clean_text(ld_event.get("name"))
        if not title:
            # og:title è il più affidabile, h1 può catturare "Accedi" dall'header
            title = self.clean_text(
                response.xpath('//meta[@property="og:title"]/@content').get()
            )
        if not title:
            # Ultimo fallback: h1 dentro il content area (non header nav)
            title = self.clean_text(
                response.css("article h1::text").get()
                or response.css(".node__content h1::text").get()
                or response.css("main h1::text").get()
            )

        if not title or title.lower() in ("accedi", "login"):
            self.logger.warning(f"Titolo non trovato o invalido: {response.url}")
            return

        # ── Descrizione ───────────────────────────────────────────────────────
        description = self.clean_text(ld_event.get("description"))
        if not description:
            description = self.clean_text(
                response.xpath('//meta[@property="og:description"]/@content').get()
            )
        if not description:
            # Drupal: campo body / content area / paragrafi post-titolo
            desc_parts = response.css("article p::text").getall()
            if desc_parts:
                description = self.clean_text(" ".join(desc_parts))

        # ── Date ───────────────────────────────────────────────────────────────
        date_start = self.parse_date_iso(ld_event.get("startDate", ""))
        date_end = self.parse_date_iso(ld_event.get("endDate", ""))

        # Orario dal JSON-LD
        start_iso = ld_event.get("startDate", "")
        time_match = re.search(r"T(\d{2}:\d{2})", start_iso)
        if time_match and date_start:
            date_start = f"{date_start} {time_match.group(1)}"

        # Fallback HTML: icona when + testo data
        quando_html = self._extract_quando_html(response)
        if not date_start and quando_html.get("date_start"):
            date_start = quando_html["date_start"]
        if not date_end and quando_html.get("date_end"):
            date_end = quando_html["date_end"]

        time_start = self._extract_time_start(response)
        if time_start and date_start and " " not in date_start:
            date_start = f"{date_start} {time_start}"

        date_display = quando_html.get("display")

        if date_end == date_start:
            date_end = None

        # ── Location ───────────────────────────────────────────────────────────
        location = ld_event.get("location") or {}
        location_name = self.clean_text(location.get("name"))
        address_obj = location.get("address") or {}
        location_address = self.clean_text(address_obj.get("streetAddress"))
        city_raw = address_obj.get("addressLocality", "")
        city = city_raw.title() if city_raw else None

        # Fallback HTML: icona where + testo location
        dove_html = self._extract_dove_html(response)
        location_name = location_name or dove_html.get("name")
        location_address = location_address or dove_html.get("address")
        city = city or dove_html.get("city")

        # Coordinate
        geo = location.get("geo") or {}
        location_coords = None
        if geo.get("latitude") and geo.get("longitude"):
            location_coords = {
                "lat": float(geo["latitude"]),
                "lng": float(geo["longitude"]),
            }

        # ── Immagine ───────────────────────────────────────────────────────────
        image_data = ld_event.get("image") or {}
        if isinstance(image_data, dict):
            image_url = image_data.get("url")
        else:
            image_url = str(image_data) if image_data else None
        if not image_url:
            image_url = response.xpath('//meta[@property="og:image"]/@content').get()

        # ── Integrazioni HTML ──────────────────────────────────────────────────
        category = self._extract_category(response)
        price = self._extract_price(response)
        contatti = self._extract_contatti(response)
        section_extra = self._extract_section_extra(response)

        # Hash
        uuid = self.generate_uuid(title or "", date_start or "", location_name or "")
        content_hash = self.generate_content_hash(description or "", price or "", time_start or "")

        # Dove raw
        dove_parts = [location_name, location_address]
        dove_raw = ", ".join(p for p in dove_parts if p) or None

        # Costruzione EventItem con struttura nested
        item = self.create_item(
            uuid=uuid,
            title=title,
            data={
                "description": description,
                "category": category,
                "image_url": image_url,
                "dates": {
                    "date_start": date_start or "",
                    "date_end": date_end or "",
                    "date_display": date_display or "",
                },
                "city": {
                    "city_name": city,
                    "location_name": location_name,
                    "location_address": location_address,
                    "location_coords": location_coords,
                },
                "section": {
                    "quando": quando_html.get("display"),
                    "dove": dove_raw,
                    "orari": section_extra.get("orari"),
                    "price": price,
                    "contatti": contatti.get("raw"),
                    "phone": contatti.get("phone"),
                    "website": contatti.get("website"),
                    "facebook": section_extra.get("facebook"),
                    "allegati": section_extra.get("allegati"),
                    "altri_link": section_extra.get("altri_link"),
                },
            },
            meta={
                "content_hash": content_hash,
                "url": response.url,
                "category": category[0] if category else "evento",
                "source": self.source_name,
            },
        )

        yield item

    # =========================================================================
    # METODI ESTRAZIONE HTML (integrativi)
    # =========================================================================

    def _extract_section_extra(self, response) -> dict:
        """Estrae campi Drupal: orari, allegati, facebook, sito web."""
        extra: dict[str, str | list[str] | None] = {
            "orari": None,
            "allegati": None,
            "facebook": None,
            "altri_link": None,
        }

        # Orari (field-orario-apertura)
        extra["orari"] = self.clean_text(
            response.css(".field--name-field-orario-apertura .field__item").xpath("string()").get()
        )

        # Allegati (field-allegati, possono essere multipli)
        allegati_links = response.css(".field--name-field-allegati a")
        if allegati_links:
            allegati = []
            for link in allegati_links:
                href = link.attrib.get("href", "")
                title = self.clean_text(link.attrib.get("title", "")) or self.clean_text(link.css("::text").get())
                if href:
                    full_url = f"{self.BASE_URL}{href}" if href.startswith("/") else href
                    allegati.append({"url": full_url, "title": title})
            if allegati:
                extra["allegati"] = allegati

        # Facebook (field-pagina-fb)
        fb_link = response.css(".field--name-field-pagina-fb a::attr(href)").get()
        if fb_link:
            extra["facebook"] = fb_link

        # Altri link (sito web già catturato in contatti, qui raccogliamo altri)
        altri = []
        sito_web = response.css(".field--name-field-sito-web a::attr(href)").get()
        if sito_web:
            altri.append(sito_web)
        if altri:
            extra["altri_link"] = altri

        return extra

    def _extract_quando_html(self, response) -> dict:
        """Estrae le date dall'HTML. Cerca icona when, h5 Quando, o pattern data."""
        quando = {"display": None, "date_start": None, "date_end": None}

        # Drupal: campo field-data con tag <time datetime="...">
        time_elements = response.css(".c-info-bar__details time.datetime")
        if time_elements:
            datetimes = [t.attrib.get("datetime", "") for t in time_elements]
            display_texts = [self.clean_text(t.css("::text").get()) for t in time_elements]

            if datetimes:
                quando["date_start"] = self.parse_date_iso(datetimes[0])
                # Orario dal datetime ISO
                time_match = re.search(r"T(\d{2}:\d{2})", datetimes[0])
                if time_match and quando["date_start"] and time_match.group(1) != "12:00":
                    quando["date_start"] = f"{quando['date_start']} {time_match.group(1)}"

            if len(datetimes) >= 2:
                quando["date_end"] = self.parse_date_iso(datetimes[1])

            quando["display"] = " - ".join(t for t in display_texts if t)
            return quando

        # Fallback: h5 "Quando" → testo con date DD/MM/YYYY
        raw_text = self.clean_text(response.xpath(
            '//h5[contains(text(), "Quando")]/ancestor::div[1]'
        ).xpath("string()").get())

        if raw_text:
            # Rimuovi label "Quando"
            raw_text = self.clean_text(raw_text.replace("Quando", ""))
            quando["display"] = raw_text
            dates = self.extract_dates_from_text(raw_text)
            if dates:
                quando["date_start"] = dates[0]
            if len(dates) >= 2:
                quando["date_end"] = dates[1]

            times = re.findall(r"(\d{1,2}:\d{2})", raw_text)
            if times and quando["date_start"] and " " not in quando["date_start"]:
                quando["date_start"] = f"{quando['date_start']} {times[0]}"

        return quando

    def _extract_dove_html(self, response) -> dict:
        """Estrae location dall'HTML. Cerca icona where, h5 Dove, o pattern testo."""
        dove = {"name": None, "address": None, "city": None}

        # Drupal: span.organization (venue) e span.address-line1 (indirizzo)
        organization = self.clean_text(
            response.css(".c-info-bar__details span.organization::text").get()
        )
        address_line = self.clean_text(
            response.css(".c-info-bar__details span.address-line1::text").get()
        )

        if organization or address_line:
            dove["name"] = organization
            if address_line:
                dove["address"], dove["city"] = self._split_address_city(address_line)
            return dove

        # Fallback: h5 "Dove" → testo
        where_text = self.clean_text(response.xpath(
            '//h5[contains(text(), "Dove")]/ancestor::div[1]'
        ).xpath("string()").get())

        if where_text:
            where_text = self.clean_text(where_text.replace("Dove", ""))
            lines = [l.strip() for l in where_text.split("\n") if l.strip()]
            if lines:
                dove["name"] = lines[0]
            if len(lines) > 1:
                dove["address"] = lines[1]

        return dove

    def _split_address_city(self, address_line: str) -> tuple[str | None, str | None]:
        """
        Separa indirizzo e città da stringhe come:
        - "Via V. Emanuele 3, Rota d'Imagna (BG)" → ("Via V. Emanuele 3", "Rota D'Imagna")
        - "piazza Martignoni 1 Camnago Volta - Como" → ("piazza Martignoni 1 Camnago Volta", "Como")
        - "Via dello sport, Brumano (BG)" → ("Via dello sport", "Brumano")
        """
        if not address_line:
            return None, None

        # Formato con " - " (trattino): indirizzo - Città
        if " - " in address_line:
            parts = address_line.rsplit(" - ", 1)
            address = self.clean_text(parts[0])
            city = self.clean_text(parts[1])
            return address, city.title() if city else None

        # Formato con ", Città (PROV)": Via X, N, Città (BG)
        city_match = re.search(r",\s*([^,]+?)(?:\s*\([A-Z]{2}\))?\s*$", address_line)
        if city_match:
            city = city_match.group(1).strip()
            address = address_line[:city_match.start()].strip()
            return self.clean_text(address), city.title()

        return address_line, None

    def _extract_contatti(self, response) -> dict:
        """Estrae la sezione 'Contatti' dall'HTML."""
        contatti = {"raw": None, "phone": None, "website": None}

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
        """Estrae la categoria dall'HTML Drupal."""
        cat = (
            response.css(".field--name-field-temi a::text").get()
            or response.css(".field-name-field-temi a::text").get()
            or response.css(".field--name-field-tipologia a::text").get()
        )
        cat = self.clean_text(cat)
        return [cat] if cat else []

    def _extract_price(self, response) -> Optional[str]:
        """Estrae il prezzo dall'HTML."""
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
            price_text = (
                response.css(".field--name-field-prezzo::text").get()
                or response.css(".field-name-field-prezzo .field-item::text").get()
            )

        return self.clean_text(price_text)

    def _extract_time_start(self, response) -> Optional[str]:
        """Estrae l'orario di inizio dall'HTML."""
        time_text = response.xpath(
            '//h4[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "orari")]'
            '/following-sibling::p[1]/text()'
        ).get()
        time_text = self.clean_text(time_text)

        if not time_text:
            return None

        match = re.match(r"^(\d{1,2}:\d{2})", time_text)
        return match.group(1) if match else time_text
