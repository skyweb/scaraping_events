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
        """Avvia il listing per ogni categoria dalla pagina"""
        for category in self.CATEGORIES:
            yield scrapy.Request(
                f"{self.BASE_URL}/it/tipo-evento/{category}?page=1",
                callback=self._parse_listing,
                meta={"page": 1, "category": category},
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



        # Coordinate (POINT WKT o variabili JS)
        location_coords = self._extract_coords(response)

        informazioni = self._extract_informazioni(response)

        # Contatti dal blocco informazioni (estratti a livello data, non dentro section)
        contacts = informazioni.pop("contatti", None)

        # Orari (estratti dentro dates, non dentro section)
        orari = informazioni.pop("orari", None)

        # Hash
        uuid = self.generate_uuid(title, date_start or "", location_name or "Roma")
        content_hash = self.generate_content_hash(description or "", "", "")

        item = self.create_item(
            uuid=uuid,
            title=title,
            data={
                "description": description,
                "category": [listing_category],
                "cover_url": image_url,
                "dates": {
                    "date_start": date_start or "",
                    "date_end": date_end or "",
                    "date_display": date_display or "",
                    "orari": orari,
                },
                "city": {
                    "city_name": "Roma",
                    "location_name": (informazioni.get("dove") or {}).get("nome"),
                    "location_address": location_address,
                    "location_coords": location_coords,
                    "location_url": ("https://www.turismoroma.it" + url) if (url := (informazioni.get("dove") or {}).get("url")) else None,
                },
                "contacts": contacts,

            },
            meta={
                "content_hash": content_hash,
                "url": response.url,
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

    def _extract_informazioni(self, response) -> dict:
        """Estrae il blocco #informazioni strutturato: dove, contatti, orari.

        Mappa i campi Drupal field-name-field-*-08 in un dict JSON:
        {
            "dove": {"nome": "Museo del Corso", "indirizzo": "VIA ...", "url": "/it/luoghi/..."},
            "contatti": [{"label": "Telefono", "value": "06 ...", "url": null}, ...],
            "orari": "testo orari...",
        }
        """
        info: dict = {}

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
            contatti: list = []
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
                    contatti.append(entry)

            if contatti:
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

        return info
