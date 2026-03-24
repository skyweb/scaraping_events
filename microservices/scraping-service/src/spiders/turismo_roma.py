# -*- coding: utf-8 -*-
"""
Spider per turismoroma.it - Portale turistico di Roma.

Il sito usa Drupal 7. Nessuna API REST esposta e nessun JSON-LD.
Lo spider naviga le categorie di eventi con paginazione ?page=N
e scrapa le pagine dettaglio per i dati completi.

Utilizzo:
    scrapy crawl turismo_roma
    scrapy crawl turismo_roma -a max_pages=5

Parametri:
    max_pages: Numero massimo di pagine per OGNI categoria (default: 3)
"""

import re
from typing import Optional

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS, parse_italian_date_time


class TurismoRomaSpider(BaseEventSpider):
    """
    Spider per turismoroma.it (Drupal 7).

    Strategia:
    1. Naviga le pagine di categoria (/it/tipo-evento/{cat}?page=N)
    2. Per ogni card, estrae il link alla pagina dettaglio
    3. Dal dettaglio estrae date (italiano), location (microdata), descrizione, immagine
    """

    name = "turismo_roma"
    source_name = "turismo_roma"
    allowed_domains = ["www.turismoroma.it"]

    BASE_URL = "https://www.turismoroma.it"

    # Categorie di eventi disponibili
    CATEGORIES = [
        "manifestazioni",
        "mostre",
        "musica",
        "teatro",
        "danza",
        "sport",
    ]

    custom_settings = {**DEFAULT_CRAWL_SETTINGS}

    def __init__(self, max_pages: str = "3", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self._seen_urls: set[str] = set()

    def start_requests(self):
        """Avvia il listing per ogni categoria dalla pagina 0."""
        for category in self.CATEGORIES:
            yield scrapy.Request(
                f"{self.BASE_URL}/it/tipo-evento/{category}?page=0",
                callback=self._parse_listing,
                meta={"page": 0, "category": category},
            )

    def _parse_listing(self, response):
        """Parsa la pagina listing per una categoria."""
        cards = response.css("div.views-row")
        new_count = 0
        category = response.meta["category"]

        for card in cards:
            href = card.css("div.snodo_titolo a::attr(href)").get()
            if not href:
                continue

            full_url = response.urljoin(href)
            if full_url in self._seen_urls:
                continue
            self._seen_urls.add(full_url)
            new_count += 1

            yield scrapy.Request(
                full_url,
                callback=self._parse_detail,
                meta={"listing_category": category},
            )

        page = response.meta["page"]
        self.logger.info(f"[{category}] Pagina {page}: {new_count} nuovi eventi")

        # Paginazione
        has_next = response.css("li.pager-next a::attr(href)").get()
        next_page = page + 1
        if has_next and next_page < self.max_pages:
            yield scrapy.Request(
                f"{self.BASE_URL}/it/tipo-evento/{category}?page={next_page}",
                callback=self._parse_listing,
                meta={"page": next_page, "category": category},
            )

    def _parse_detail(self, response):
        """Parsa la pagina dettaglio evento."""
        listing_category = response.meta.get("listing_category", "evento")

        # Titolo — og:title è il più affidabile
        title = self.clean_text(
            response.xpath('//meta[@property="og:title"]/@content').get()
        )
        if not title:
            title = self.clean_text(response.css("h1::text").get())
        if not title:
            return

        # Descrizione
        desc_el = response.css(".field-name-field-descrizione .field-item")
        description = self.clean_text(desc_el.xpath("string()").get()) if desc_el else None

        # Immagine
        image_url = response.css(
            "#redazione .field-name-field-immagine-copertina img::attr(src)"
        ).get()

        # Date (formato italiano: "dal DD Mese YYYY al DD Mese YYYY")
        date_start, date_end, date_display = self._extract_dates(response)

        # Location (microdata PostalAddress)
        location_name = self.clean_text(
            response.css('.location.vcard span.fn[itemprop="name"]::text').get()
        )
        location_address = self.clean_text(
            response.css('span[itemprop="streetAddress"]::text').get()
        )

        # Venue dal link /it/luoghi/
        if not location_name:
            location_name = self.clean_text(
                response.css('.field-name-field-sedi-08 a::text').get()
            )

        # Coordinate (POINT WKT o variabili JS)
        location_coords = self._extract_coords(response)

        # Blocco #informazioni: quando, dove, contatti, orari
        informazioni = self._extract_informazioni(response)

        # Orari (già estratti sopra, ma anche nel blocco informazioni)
        orari = informazioni.get("orari")

        # Contatti dal blocco informazioni
        contatti = informazioni.get("contatti", {})

        # Slug
        slug = response.url.rstrip("/").split("/")[-1] or "evento"

        # Hash
        uuid = self.generate_uuid(title, date_start or "", location_name or "Roma")
        content_hash = self.generate_content_hash(description or "", "", "")

        item = self.create_item(
            uuid=uuid,
            title=title,
            data={
                "description": description,
                "category": [listing_category],
                "image_url": image_url,
                "dates": {
                    "date_start": date_start or "",
                    "date_end": date_end or "",
                    "date_display": date_display or "",
                },
                "city": {
                    "city_name": "Roma",
                    "location_name": location_name,
                    "location_address": location_address,
                    "location_coords": location_coords,
                },
                "section": {
                    "informazioni": informazioni,
                    "orari": orari,
                    "phone": contatti.get("phone"),
                    "email": contatti.get("email"),
                    "website": contatti.get("website"),
                },
            },
            meta={
                "content_hash": content_hash,
                "url": response.url,
                "event_id": slug,
                "category": listing_category,
                "source": self.source_name,
            },
        )

        yield item

    def _extract_dates(self, response) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Estrae date dalla sezione periodo (formato italiano)."""
        periodo_el = response.css(".field-name-field-periodo-08 .field-item")
        if not periodo_el:
            return None, None, None

        display = self.clean_text(periodo_el.xpath("string()").get())
        date_start = None
        date_end = None

        # Prova span.date-display-start / end
        start_text = self.clean_text(
            periodo_el.css("span.date-display-start::text").get()
        )
        end_text = self.clean_text(
            periodo_el.css("span.date-display-end::text").get()
        )

        if start_text:
            # Rimuove "dal " / "al " prefissi
            clean_start = re.sub(r"^(dal|al|from|to)\s+", "", start_text, flags=re.IGNORECASE)
            date_start, _ = parse_italian_date_time(clean_start)
        if end_text:
            clean_end = re.sub(r"^(dal|al|from|to)\s+", "", end_text, flags=re.IGNORECASE)
            date_end, _ = parse_italian_date_time(clean_end)

        # Fallback: cerca date nel testo display
        if not date_start and display:
            dates = self.extract_dates_from_text(display)
            if dates:
                date_start = dates[0]
            if len(dates) >= 2:
                date_end = dates[1]

        if date_end == date_start:
            date_end = None

        return date_start, date_end, display

    def _extract_coords(self, response) -> Optional[dict]:
        """Estrae coordinate dal DOM (WKT) o dal JS inline."""
        # WKT: POINT (lon lat)
        wkt_text = self.clean_text(
            response.css(".field-name-field-coordinate-08 .field-item::text").get()
        )
        if wkt_text:
            match = re.search(r"POINT\s*\(\s*([\d.]+)\s+([\d.]+)\s*\)", wkt_text)
            if match:
                return {"lat": float(match.group(2)), "lng": float(match.group(1))}

        # JS inline: var latmap = ...; var lonmap = ...;
        for script in response.css("script::text").getall():
            lat_match = re.search(r"var\s+latmap\s*=\s*([\d.]+)", script)
            lon_match = re.search(r"var\s+lonmap\s*=\s*([\d.]+)", script)
            if lat_match and lon_match:
                return {"lat": float(lat_match.group(1)), "lng": float(lon_match.group(1))}

        return None

    def _extract_contatti(self, response) -> dict:
        """Estrae contatti dalla sezione contatti (double-field)."""
        contatti: dict[str, Optional[str]] = {"phone": None, "email": None, "website": None}

        contatti_section = response.css(".field-name-field-contatti-08 .field-item")
        if not contatti_section:
            return contatti

        for item in contatti_section.css(".field-item"):
            label = self.clean_text(item.css(".double-field-first::text").get())
            value_el = item.css(".double-field-second")
            if not label or not value_el:
                continue

            label_lower = label.lower()

            if "sito" in label_lower or "web" in label_lower:
                contatti["website"] = value_el.css("a::attr(href)").get()
            elif "telefon" in label_lower or "tel" in label_lower:
                contatti["phone"] = self.clean_text(value_el.xpath("string()").get())
            elif "email" in label_lower or "mail" in label_lower:
                contatti["email"] = self.clean_text(value_el.xpath("string()").get())

        return contatti

    def _extract_informazioni(self, response) -> dict:
        """Estrae il blocco #informazioni strutturato: quando, dove, contatti, orari.

        Mappa i campi Drupal field-name-field-*-08 in un dict JSON:
        {
            "quando": {"display": "dal 21 Novembre 2025 al 12 Aprile 2026", ...},
            "dove": {"nome": "Museo del Corso", "indirizzo": "VIA ...", "url": "/it/luoghi/..."},
            "contatti": {"website": "...", "phone": "...", "email": "...", "entries": [...]},
            "orari": "testo orari...",
            "orari_dettaglio": ["Mercoledì – Venerdì: 11.00 – 19.00", ...]
        }
        """
        info: dict = {}

        # --- Quando ---
        periodo_el = response.css(".field-name-field-periodo-08 .field-item")
        if periodo_el:
            quando = {"display": self.clean_text(periodo_el.xpath("string()").get())}
            start_text = self.clean_text(periodo_el.css("span.date-display-start::text").get())
            end_text = self.clean_text(periodo_el.css("span.date-display-end::text").get())
            if start_text:
                clean_start = re.sub(r"^(dal|al)\s+", "", start_text, flags=re.IGNORECASE).strip()
                quando["data_inizio_raw"] = clean_start
            if end_text:
                clean_end = re.sub(r"^(dal|al)\s+", "", end_text, flags=re.IGNORECASE).strip()
                quando["data_fine_raw"] = clean_end
            info["quando"] = quando

        # --- Dove ---
        sede_el = response.css(".field-name-field-sedi-08")
        coord_el = response.css(".field-name-field-coordinate-08")
        if sede_el or coord_el:
            dove: dict = {}
            sede_link = sede_el.css("a") if sede_el else None
            if sede_link:
                dove["nome"] = self.clean_text(sede_link.css("::text").get())
                dove["url"] = sede_link.attrib.get("href")
            indirizzo = self.clean_text(
                response.css('span[itemprop="streetAddress"]::text').get()
            )
            if indirizzo:
                dove["indirizzo"] = indirizzo
            if coord_el:
                wkt = self.clean_text(coord_el.css(".field-item::text").get())
                if wkt:
                    match = re.search(r"POINT\s*\(\s*([\d.]+)\s+([\d.]+)\s*\)", wkt)
                    if match:
                        dove["coordinate"] = {"lat": float(match.group(2)), "lng": float(match.group(1))}
            if dove:
                info["dove"] = dove

        # --- Contatti ---
        contatti_el = response.css(".field-name-field-contatti-08")
        if contatti_el:
            contatti: dict = {"entries": []}
            for item_el in contatti_el.css(".field-item .container-inline"):
                label = self.clean_text(item_el.css(".double-field-first::text").get())
                value_text = self.clean_text(item_el.css(".double-field-second").xpath("string()").get())
                value_href = item_el.css("a::attr(href)").get()

                entry = {}
                if label:
                    entry["label"] = label.rstrip(":")
                if value_text:
                    entry["value"] = value_text
                if value_href:
                    entry["url"] = value_href
                if entry:
                    contatti["entries"].append(entry)

                # Mappa ai campi standard
                if label:
                    label_lower = label.lower()
                    if "sito" in label_lower or "web" in label_lower:
                        contatti["website"] = value_href or value_text
                    elif "telefon" in label_lower or "tel" in label_lower:
                        contatti["phone"] = value_text
                    elif "email" in label_lower or "mail" in label_lower:
                        contatti["email"] = value_text
                    elif "facebook" in label_lower:
                        contatti["facebook"] = value_href or value_text
                    elif "instagram" in label_lower:
                        contatti["instagram"] = value_href or value_text

            if not contatti["entries"]:
                del contatti["entries"]
            info["contatti"] = contatti

        # --- Orari ---
        orari_el = response.css(".field-name-field-orario-08 .field-item")
        if orari_el:
            orari_text = self.clean_text(orari_el.xpath("string()").get())
            orari_paragraphs = []
            for p in orari_el.css("p"):
                p_text = self.clean_text(p.xpath("string()").get())
                if p_text:
                    orari_paragraphs.append(p_text)
            info["orari"] = orari_text
            if orari_paragraphs:
                info["orari_dettaglio"] = orari_paragraphs

        return info
