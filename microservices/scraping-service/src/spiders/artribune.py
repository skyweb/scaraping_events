# -*- coding: utf-8 -*-
"""
Spider per Artribune.com - Eventi culturali e mostre d'arte.

Artribune è un magazine online dedicato all'arte e alla cultura.
Lo spider usa le API WordPress REST per ottenere la lista eventi,
arricchisce i dati con un endpoint custom e visita le pagine dettaglio.

Utilizzo:
    scrapy crawl artribune
    scrapy crawl artribune -a max_pages=5

Parametri:
    max_pages: Numero massimo di pagine da scrapare (default: tutte)
    per_page: Eventi per pagina (default: 100, max API: 100)
"""

import re

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class ArtribuneSpider(BaseEventSpider):
    """
    Spider per Artribune.com.

    Flusso:
    1. Scarica endpoint custom per dati strutturati (place, dates)
    2. Scarica lista eventi dall'API WP REST con paginazione
    3. Per ogni evento, visita la pagina per dettagli aggiuntivi
    """

    name = "artribune"
    source_name = "artribune"
    allowed_domains = ["artribune.com"]

    custom_settings = {
        **DEFAULT_CRAWL_SETTINGS,
        "DOWNLOAD_DELAY": 2.0,
    }

    def __init__(
        self,
        max_pages: int = None,
        per_page: int = 100,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.per_page = min(int(per_page), 100)
        self.max_pages = int(max_pages) if max_pages else None
        self.custom_api_data: dict[str, dict] = {}

    def start_requests(self):
        """Inizia con l'endpoint custom per dati strutturati."""
        yield scrapy.Request(
            "https://www.artribune.com/wp-json/a7e/v1/events",
            callback=self.parse_custom_api,
            priority=10,
        )

    def parse_custom_api(self, response):
        """Parsa endpoint custom e memorizza dati strutturati."""
        try:
            data = response.json()
            events = data.get("events", []) if isinstance(data, dict) else data

            for event in events:
                url = event.get("url")
                if url:
                    self.custom_api_data[url] = {
                        "place": event.get("place", {}),
                        "dates_html": event.get("dates"),
                        "image_html": event.get("image"),
                        "excerpt": event.get("excerpt"),
                    }

            self.logger.info(f"API custom: {len(self.custom_api_data)} eventi memorizzati")

        except Exception as e:
            self.logger.warning(f"Errore parsing API custom: {e}")

        # Avvia scraping dall'API standard
        yield scrapy.Request(
            f"https://www.artribune.com/wp-json/wp/v2/event?per_page={self.per_page}&page=1",
            callback=self.parse,
        )

    def parse(self, response):
        """Parsa lista eventi dall'API WP REST."""
        try:
            events_list = response.json()
            total_pages = int(response.headers.get("X-WP-TotalPages", b"0").decode())

            page_match = re.search(r"[?&]page=(\d+)", response.url)
            current_page = int(page_match.group(1)) if page_match else 1

            self.logger.info(f"Pagina {current_page}/{total_pages}")

            if not events_list:
                return

            for event_data in events_list:
                url = event_data.get("link")
                title_obj = event_data.get("title", {})
                title = title_obj.get("rendered") if isinstance(title_obj, dict) else title_obj

                # Dati dall'API custom
                custom = self.custom_api_data.get(url, {})

                api_data = {
                    "url": url,
                    "title": self.clean_text(title),
                    "custom": custom,
                }

                if url:
                    yield response.follow(
                        url,
                        callback=self.parse_event_detail,
                        meta={"api_data": api_data},
                    )

            # Paginazione
            max_pages = self.max_pages or total_pages
            if current_page < max_pages:
                next_page = current_page + 1
                yield scrapy.Request(
                    f"https://www.artribune.com/wp-json/wp/v2/event?per_page={self.per_page}&page={next_page}",
                    callback=self.parse,
                )

        except Exception as e:
            self.logger.error(f"Errore parsing API: {e}")

    def parse_event_detail(self, response):
        """Estrae dettagli dalla pagina evento e costruisce l'EventItem nested."""
        api_data = response.meta["api_data"]
        custom = api_data.get("custom", {})
        url = api_data["url"]
        title = api_data["title"]

        # ── Location dall'API custom ───────────────────────────────────────────
        location_name = None
        location_address = None
        city = None

        place = custom.get("place", {})
        if isinstance(place, dict):
            location_name = place.get("title")
            place_map = place.get("map", {})
            if isinstance(place_map, dict):
                location_address = place_map.get("address")
            place_city = place.get("city", {})
            if isinstance(place_city, dict):
                city_title = place_city.get("title", "")
                city = re.sub(r"\s*\([A-Z]{2}\)$", "", city_title).strip() or None

        # ── Date dall'API custom ───────────────────────────────────────────────
        date_start = None
        date_end = None
        dates_html = custom.get("dates_html", "")
        if dates_html and "<time" in dates_html:
            dt_matches = re.findall(r'datetime=["\'](\d{4}-\d{2}-\d{2})["\']', dates_html)
            if len(dt_matches) >= 1:
                date_start = dt_matches[0]
            if len(dt_matches) >= 2:
                date_end = dt_matches[1]

        # ── Immagine dall'API custom ───────────────────────────────────────────
        image_url = None
        image_html = custom.get("image_html", "")
        if image_html and "<img" in image_html:
            img_urls = re.findall(r'src=["\'](.*?)["\']', image_html)
            if img_urls:
                image_url = img_urls[0]

        # ── JSON-LD Event ──────────────────────────────────────────────────────
        price = None
        event_obj = self.extract_jsonld_node(response, "Event")
        if event_obj:
            # Immagine fallback
            if not image_url:
                ld_images = event_obj.get("image")
                if isinstance(ld_images, list) and ld_images:
                    image_url = ld_images[0]
                elif isinstance(ld_images, str):
                    image_url = ld_images

            # Prezzo
            offers = event_obj.get("offers", {})
            if isinstance(offers, dict) and offers.get("price"):
                price = str(offers["price"])
            elif isinstance(offers, list) and offers and offers[0].get("price"):
                price = str(offers[0]["price"])

            # Date fallback
            if not date_start:
                date_start = self.parse_date_iso(event_obj.get("startDate"))
            if not date_end:
                date_end = self.parse_date_iso(event_obj.get("endDate"))

        # ── Widget HTML (.c-widget_content) ──────────────────────────────────
        widget = self._extract_widget(response)

        # Location dal widget (dd separati: venue e indirizzo)
        if not location_name:
            location_name = widget.get("location_name")
        if not location_address:
            location_address = widget.get("location_address")

        # Location fallback
        if not location_name:
            location_name = self.clean_text(response.xpath(
                '//header//ul[contains(@class, "-meta")]//a[contains(@href, "/museo-galleria-arte/")]/text()'
            ).get())

        # Città dal breadcrumb
        if not city:
            city_breadcrumb = self.clean_text(response.xpath(
                '//nav[contains(@class, "c-breadcrumb")]/a[contains(@href, "/mostre/")]/text()'
            ).get())
            if city_breadcrumb:
                city = city_breadcrumb

        # Categoria dal widget
        category = widget.get("category", [])

        # Date dal widget
        if not date_start and widget.get("date_start"):
            date_start = widget["date_start"]
        if not date_end and widget.get("date_end"):
            date_end = widget["date_end"]

        date_display = widget.get("date_display", "")
        orari = widget.get("orari")
        artisti = widget.get("artisti", [])

        if date_end == date_start:
            date_end = None

        # Descrizione
        description = None
        content_div = response.css(".c-content.-post")
        if content_div:
            description = "".join(content_div.xpath("node()").getall())

        # Immagine fallback
        if not image_url:
            image_url = response.css(".c-featured img::attr(src)").get()

        # Prezzo fallback HTML
        if not price:
            price_text = response.xpath(
                '//text()[contains(., "Biglietti") or contains(., "Costo")]/following::text()[1]'
            ).get()
            if price_text:
                price = self.clean_text(price_text)

        # Slug

        # Hash
        uuid = self.generate_uuid(title or "", date_start or "", location_name or "")
        content_hash = self.generate_content_hash(description or "", price or "", "")

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
                    "date_display": date_display,
                },
                "city": {
                    "city_name": city,
                    "location_name": location_name,
                    "location_address": location_address,
                },
                "section": {
                    "price": price,
                    "orari": orari,
                    "artisti": artisti,
                },
            },
            meta={
                "content_hash": content_hash,
                "url": url or response.url,
                "event_id": slug,
                "category": category[0] if category else "evento",
                "source": self.source_name,
            },
        )

        yield item

    def _extract_widget(self, response) -> dict:
        """Estrae dati strutturati dal widget c-widget_content (Luogo, Date, Artisti, Generi)."""
        result: dict = {
            "location_name": None,
            "location_address": None,
            "date_start": None,
            "date_end": None,
            "date_display": "",
            "orari": None,
            "artisti": [],
            "category": [],
        }

        # Il widget dettagli ha dl diretti (non quello con card correlati che ha u-cq)
        widget_dls = response.xpath(
            '//div[contains(@class, "c-widget_content") and not(contains(@class, "u-cq"))]/dl'
        )
        if not widget_dls:
            widget_dls = response.css(".c-widget_content dl")
        for dl in widget_dls:
            dt_text = self.clean_text(dl.xpath("string(.//dt)").get())
            if not dt_text:
                continue
            dt_text = dt_text.strip()

            dds = dl.css("dd")

            # ── Luogo ──
            if "Luogo" in dt_text:
                if dds:
                    # Primo dd: nome venue (link museo/galleria)
                    venue_link = dds[0].css("a::text").get()
                    result["location_name"] = self.clean_text(venue_link or dds[0].xpath("string()").get())
                if len(dds) >= 2:
                    # Secondo dd: indirizzo (link Google Maps)
                    addr_text = self.clean_text(dds[1].xpath("string()").get())
                    if addr_text:
                        result["location_address"] = addr_text.replace("(Clicca qui per la mappa)", "").strip()

            # ── Date ──
            elif "Date" in dt_text:
                if dds:
                    # Primo dd: "Dal <time>12/03/2026</time> al <time>09/05/2026</time>"
                    date_dd = dds[0]
                    result["date_display"] = self.clean_text(date_dd.xpath("string()").get())

                    time_tags = date_dd.css("time")
                    if time_tags:
                        result["date_start"] = time_tags[0].attrib.get("datetime")
                    if len(time_tags) >= 2:
                        result["date_end"] = time_tags[1].attrib.get("datetime")

                if len(dds) >= 2:
                    # Secondo dd: orari (es. "Open from Tuesday to Saturday, 10.30am - 6.30pm")
                    orari_text = self.clean_text(dds[1].xpath("string()").get())
                    if orari_text:
                        result["orari"] = orari_text

            # ── Artisti ──
            elif "Artisti" in dt_text:
                for dd in dds:
                    name = self.clean_text(dd.css("a::text").get() or dd.xpath("string()").get())
                    if name:
                        result["artisti"].append(name)

            # ── Generi ──
            elif "Generi" in dt_text:
                for dd in dds:
                    text = self.clean_text(dd.xpath("string()").get())
                    if text:
                        result["category"] = [g.strip() for g in text.split(",")]

        return result

    def _extract_event_info(self, response) -> dict:
        """Estrae informazioni evento dal widget HTML."""
        event_info = {}
        info_dls = response.xpath('//div[contains(@class, "c-widget_content")]/dl')

        for dl in info_dls:
            key = dl.xpath(
                './/dt//span[contains(@class, "sr") or contains(@class, "hidden")]//text()'
            ).get()

            if not key:
                dt_texts = dl.xpath(".//dt/text() | .//dt/span/text()").getall()
                key = " ".join([t.strip() for t in dt_texts if t.strip()])

            if not key:
                key = dl.xpath(".//dt/@title | .//dt/@aria-label").get()

            dds = dl.xpath(".//dd")
            if not key and len(dds) >= 2:
                first_dd_text = dds[0].xpath(".//text()").getall()
                key = " ".join([t.strip() for t in first_dd_text if t.strip()])
                dds = dds[1:]

            if key:
                key = key.strip()
                values = []
                for dd in dds:
                    text_parts = dd.xpath(".//text()").getall()
                    text = " ".join([t.strip() for t in text_parts if t.strip()])
                    text = text.replace("(Clicca qui per la mappa)", "").strip()
                    if text:
                        values.append(text)

                if values:
                    event_info[key] = "\n".join(values)

        return event_info
