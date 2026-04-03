# -*- coding: utf-8 -*-
"""
Spider per suedtirol.info - Portale turistico dell'Alto Adige / Südtirol.

Il sito usa Adobe AEM con Algolia. Le card eventi sono SSR e le pagine
dettaglio hanno JSON-LD Event + accordion "Tutto quello che devi sapere".

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

        # Location da JSON-LD
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

        # Calendario date individuali
        calendar = self._extract_calendar(response)

        # "Tutto quello che devi sapere" dall'accordion
        da_sapere = self._extract_da_sapere(response)

        # Location e coordinate dalla mappa
        location_name = da_sapere.pop("_location_name", None)
        location_address = da_sapere.pop("_location_address", None)
        location_coords = da_sapere.pop("_location_coords", None)

        uuid = self.generate_uuid(title, date_start or "", city or "")
        content_hash = self.generate_content_hash(description or "", "", "")

        # Section: solo dati non ricollocabili
        section = {}
        if calendar:
            section["calendar"] = calendar
        if da_sapere:
            section["da_sapere"] = da_sapere

        yield self.create_item(
            uuid=uuid, title=title,
            data={
                "description": description, "category": [], "cover_url": image_url,
                "dates": {"date_start": date_start or "", "date_end": date_end or "", "date_display": ""},
                "city": {
                    "city_name": city,
                    "location_name": location_name,
                    "location_address": location_address,
                    "location_coords": location_coords,
                },
                **({"section": section} if section else {}),
            },
            meta={
                "content_hash": content_hash,
                "url": response.url,
                "category": "evento",
                "source": self.source_name,
            },
        )

    def _extract_calendar(self, response) -> list:
        """Estrae le date individuali dalla lista date."""
        dates = []
        for item in response.css(".sdt-date-list .list-date .item"):
            date_text = self.clean_text(item.css(".date::text").get())
            hour_text = self.clean_text(item.css(".hour::text").get())
            if date_text:
                entry = {"date": date_text}
                if hour_text:
                    entry["hour"] = hour_text
                dates.append(entry)
        return dates

    def _extract_da_sapere(self, response) -> dict:
        """Estrae le info dall'accordion 'Tutto quello che devi sapere'."""
        da_sapere = {}

        for item in response.css("#sdt-pdp-event-accordion .sdt-accordion-item"):
            # Label dal button aria-label o dal testo span
            label = item.css("button::attr(aria-label)").get()
            if not label:
                label = self.clean_text(item.css("button span.sdt-font-body-ssp-regular::text").get())
            if not label:
                continue

            label_key = label.lower().strip()

            # Contenuto dal body
            body = item.css(".sdt-accordion-body")
            if not body:
                continue

            if "punto d'incontro" in label_key or "meeting" in label_key:
                da_sapere["punto_incontro"] = self.clean_text(body.css(".cmp-text").xpath("string()").get())

            elif "registrazione" in label_key or "registration" in label_key:
                da_sapere["registrazione"] = self.clean_text(body.css(".cmp-text").xpath("string()").get())

            elif "contatt" in label_key or "contact" in label_key:
                contact_name = self.clean_text(body.css(".sdt-font-text-s-bold.sdt-title::text").get())
                if contact_name:
                    da_sapere["contatti_nome"] = contact_name
                # Telefono, email, website dai link
                for link in body.css("a[href]"):
                    href = link.attrib.get("href", "")
                    if href.startswith("tel:"):
                        da_sapere["phone"] = href.replace("tel:", "")
                    elif href.startswith("mailto:"):
                        da_sapere["email"] = href.replace("mailto:", "")
                    elif href.startswith("http") and "google.com/maps" not in href:
                        da_sapere["website"] = href

            elif "posizione" in label_key or "location" in label_key or "indicazioni" in label_key:
                # Coordinate dalla mappa Leaflet
                map_el = body.css("div.sdt-map-detail[data-lat][data-lon]")
                if map_el:
                    lat = map_el.attrib.get("data-lat")
                    lon = map_el.attrib.get("data-lon")
                    if lat and lon:
                        da_sapere["_location_coords"] = {"type": "Point", "coordinates": [float(lon), float(lat)]}

                # Nome luogo e indirizzo
                loc_name = self.clean_text(body.css(".sdt-font-text-s-bold.sdt-title::text").get())
                if loc_name:
                    da_sapere["_location_name"] = loc_name
                loc_addr = self.clean_text(body.css("a.sdt-font-body-ssp-regular span::text").get())
                if loc_addr:
                    da_sapere["_location_address"] = loc_addr

            elif "portare" in label_key or "bring" in label_key:
                da_sapere["cosa_portare"] = self.clean_text(body.css(".cmp-text").xpath("string()").get())

            elif "cancellazione" in label_key or "rimborso" in label_key or "refund" in label_key:
                da_sapere["cancellazione"] = self.clean_text(body.css(".cmp-text").xpath("string()").get())

            elif "descrizione" in label_key or "service" in label_key:
                da_sapere["descrizione_servizio"] = self.clean_text(body.css(".cmp-text").xpath("string()").get())

            elif "download" in label_key:
                downloads = []
                for dl in body.css("a[href]"):
                    downloads.append({"url": dl.attrib.get("href"), "text": self.clean_text(dl.xpath("string()").get())})
                if downloads:
                    da_sapere["downloads"] = downloads

        return da_sapere
