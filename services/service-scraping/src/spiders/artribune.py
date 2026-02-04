# -*- coding: utf-8 -*-
"""
Spider per Artribune.com - Eventi culturali e mostre d'arte.

Artribune è un magazine online dedicato all'arte e alla cultura.
Lo spider usa le API WordPress REST per ottenere la lista eventi,
poi arricchisce i dati visitando le pagine di dettaglio.

Utilizzo:
    # Scrapy diretto
    scrapy crawl artribune -o output.json

    # Con limite pagine
    scrapy crawl artribune -a max_pages=5 -o output.json

    # Scrapyd
    curl http://localhost:6800/schedule.json \
        -d project=events_scraper \
        -d spider=artribune

Parametri:
    max_pages: Numero massimo di pagine da scrapare (default: tutte)
    per_page: Eventi per pagina (default: 100, max API: 100)
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Optional

import scrapy

from spiders.base import BaseEventSpider


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
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
    }

    def __init__(
        self,
        max_pages: int = None,
        per_page: int = 100,
        *args,
        **kwargs,
    ):
        """
        Inizializza lo spider.

        Args:
            max_pages: Limite pagine (None = tutte)
            per_page: Eventi per pagina (max 100)
        """
        super().__init__(*args, **kwargs)
        self.per_page = min(int(per_page), 100)  # Max API è 100
        self.max_pages = int(max_pages) if max_pages else None
        self.custom_api_data: Dict[str, dict] = {}

    def start_requests(self):
        """Inizia con l'endpoint custom per dati strutturati."""
        yield scrapy.Request(
            "https://www.artribune.com/wp-json/a7e/v1/events",
            callback=self.parse_custom_api,
            priority=10,
        )

    def parse_custom_api(self, response):
        """
        Parsa endpoint custom e memorizza dati strutturati.

        Args:
            response: Risposta JSON dall'endpoint custom
        """
        try:
            data = response.json()
            events = data.get("events", []) if isinstance(data, dict) else data

            self.logger.info(f"Endpoint custom: {len(events)} eventi con dati strutturati")

            # Memorizza per URL
            for event in events:
                url = event.get("url")
                if url:
                    self.custom_api_data[url] = {
                        "place": event.get("place", {}),
                        "dates_html": event.get("dates"),
                        "image_html": event.get("image"),
                        "excerpt": event.get("excerpt"),
                    }

            self.logger.info(f"Memorizzati {len(self.custom_api_data)} eventi dall'API custom")

        except Exception as e:
            self.logger.warning(f"Errore parsing API custom: {e}")

        # Avvia scraping dall'API standard
        yield scrapy.Request(
            f"https://www.artribune.com/wp-json/wp/v2/event?per_page={self.per_page}&page=1",
            callback=self.parse,
        )

    def parse(self, response):
        """
        Parsa lista eventi dall'API WP REST.

        Args:
            response: Risposta JSON con lista eventi
        """
        try:
            events_list = response.json()

            # Paginazione dagli header
            total_events = int(response.headers.get("X-WP-Total", b"0").decode())
            total_pages = int(response.headers.get("X-WP-TotalPages", b"0").decode())

            # Pagina corrente
            page_match = re.search(r"[?&]page=(\d+)", response.url)
            current_page = int(page_match.group(1)) if page_match else 1

            self.logger.info(f"Pagina {current_page}/{total_pages}. Totale eventi: {total_events}")

            if not events_list:
                self.logger.info("Nessun evento trovato")
                return

            for event_data in events_list:
                item = self.create_item()

                # URL
                item["url"] = event_data.get("link")

                # Titolo
                title_obj = event_data.get("title", {})
                item["title"] = title_obj.get("rendered") if isinstance(title_obj, dict) else title_obj

                # Raw data dall'API
                item["raw_data"] = {
                    "id": event_data.get("id"),
                    "slug": event_data.get("slug"),
                    "date_published": event_data.get("date"),
                }

                # Arricchisci con API custom
                custom_data = self.custom_api_data.get(item["url"], {})
                if custom_data:
                    item["raw_data"]["custom_api"] = custom_data
                    self._enrich_from_custom(item, custom_data)

                item["image_urls"] = item.get("image_urls", [])

                # Visita pagina dettaglio
                if item["url"]:
                    yield response.follow(
                        item["url"],
                        callback=self.parse_event_detail,
                        meta={"item": item},
                    )
                else:
                    item["uuid"] = self.generate_uuid(
                        item.get("title", ""),
                        item.get("date_start", ""),
                        item.get("location_name", ""),
                    )
                    item["content_hash"] = self.generate_content_hash(
                        item.get("description", ""),
                        item.get("price", ""),
                        "",
                    )
                    yield item

            # Paginazione
            max_pages = self.max_pages or total_pages
            if current_page < max_pages:
                next_page = current_page + 1
                self.logger.info(f"Richiedo pagina {next_page}")
                yield scrapy.Request(
                    f"https://www.artribune.com/wp-json/wp/v2/event?per_page={self.per_page}&page={next_page}",
                    callback=self.parse,
                )

        except Exception as e:
            self.logger.error(f"Errore parsing API: {e}")

    def _enrich_from_custom(self, item, custom_data: dict):
        """Arricchisce item con dati dall'API custom."""
        # Place
        place = custom_data.get("place", {})
        if isinstance(place, dict):
            item["location_name"] = place.get("title")

            place_map = place.get("map", {})
            if isinstance(place_map, dict):
                item["location_address"] = place_map.get("address")

            place_city = place.get("city", {})
            if isinstance(place_city, dict):
                city_title = place_city.get("title", "")
                # Rimuovi provincia tra parentesi
                item["city"] = re.sub(r"\s*\([A-Z]{2}\)$", "", city_title).strip()

        # Date da HTML
        dates_html = custom_data.get("dates_html", "")
        if dates_html and "<time" in dates_html:
            dt_matches = re.findall(r'datetime=["\'](\d{4}-\d{2}-\d{2})["\']', dates_html)
            if len(dt_matches) >= 1:
                item["date_start"] = dt_matches[0]
            if len(dt_matches) >= 2:
                item["date_end"] = dt_matches[1]
            elif len(dt_matches) == 1:
                item["date_end"] = dt_matches[0]

        # Immagini
        image_html = custom_data.get("image_html", "")
        if "image_urls" not in item:
            item["image_urls"] = []
        if image_html and "<img" in image_html:
            urls = re.findall(r'src=["\'](.*?)["\']', image_html)
            item["image_urls"].extend(urls)
            if urls and not item.get("image_url"):
                item["image_url"] = urls[0]

    def parse_event_detail(self, response):
        """
        Estrae dettagli dalla pagina evento.

        Args:
            response: Risposta HTML della pagina
        """
        item = response.meta["item"]
        self.logger.debug(f"Scraping dettaglio: {item.get('title')}")

        # 1. Prova JSON-LD
        json_ld = response.xpath(
            '//script[@type="application/ld+json" and contains(text(), "Event")]/text()'
        ).get()

        if json_ld:
            self._parse_json_ld(item, json_ld)

        # 2. Estrazione da HTML strutturato
        event_info = self._extract_event_info(response)
        if event_info:
            if "raw_data" in item and isinstance(item["raw_data"], dict):
                item["raw_data"]["event_info"] = event_info

        # Mappatura da event_info
        if not item.get("location_name"):
            item["location_name"] = event_info.get("Luogo")

        if not item.get("category") and "Generi" in event_info:
            gens = event_info["Generi"]
            if isinstance(gens, str):
                item["category"] = [g.strip() for g in gens.split(",")]

        # Città dal breadcrumb
        if not item.get("city"):
            city_breadcrumb = response.xpath(
                '//nav[contains(@class, "c-breadcrumb")]/a[contains(@href, "/mostre/")]/text()'
            ).get()
            if city_breadcrumb:
                item["city"] = city_breadcrumb.strip()

        # Date fallback
        if not item.get("date_start"):
            item["date_start"] = response.xpath("//time[1]/@datetime").get()
        if not item.get("date_end"):
            item["date_end"] = response.xpath("//time[2]/@datetime").get()

        # Location name fallback
        if not item.get("location_name"):
            loc_name = response.xpath(
                '//header//ul[contains(@class, "-meta")]//a[contains(@href, "/museo-galleria-arte/")]/text()'
            ).get()
            if loc_name:
                item["location_name"] = loc_name.strip()

        # Indirizzo
        if not item.get("location_address"):
            full_address = response.xpath(
                '//dl[dt[contains(text(), "Luogo")]]/dd[2]/text()'
            ).get()
            if full_address:
                item["location_address"] = full_address.replace(
                    "(Clicca qui per la mappa)", ""
                ).strip()

        # Descrizione
        content_div = response.css(".c-content.-post")
        if content_div:
            parts = content_div.xpath(".//p//text() | .//h2//text()").getall()
            if parts:
                full_desc = " ".join([p.strip() for p in parts if p.strip()])
                if len(full_desc) > len(item.get("description", "") or ""):
                    item["description"] = full_desc

        # Orari
        if not item.get("schedule"):
            time_match = response.xpath('//p[contains(text(), "Orari")]/text()').get()
            if time_match:
                item["schedule"] = time_match.strip()

        # Prezzo
        if not item.get("price"):
            price_text = response.xpath(
                '//text()[contains(., "Biglietti") or contains(., "Costo")]/following::text()[1]'
            ).get()
            if price_text:
                item["price"] = price_text.strip()

        # Immagini aggiuntive
        if "image_urls" not in item:
            item["image_urls"] = []

        featured_img = response.css(".c-featured img::attr(src)").get()
        if featured_img:
            item["image_urls"].append(featured_img)

        gallery_imgs = response.css(
            ".swiper-slide img::attr(src), .gallery-item img::attr(src)"
        ).getall()
        if gallery_imgs:
            item["image_urls"].extend(gallery_imgs)

        # Pulizia immagini
        clean_urls = []
        seen = set()
        for u in item.get("image_urls", []):
            if u and isinstance(u, str):
                u = u.strip()
                if u not in seen:
                    clean_urls.append(u)
                    seen.add(u)

        item["image_urls"] = clean_urls
        if not item.get("image_url") and clean_urls:
            item["image_url"] = clean_urls[0]

        # Hash finali
        item["uuid"] = self.generate_uuid(
            item.get("title", ""),
            item.get("date_start", ""),
            item.get("location_name", ""),
        )
        item["content_hash"] = self.generate_content_hash(
            item.get("description", ""),
            item.get("price", ""),
            "",
        )

        self.log_stats(item.get("city"))
        yield item

    def _parse_json_ld(self, item, json_ld: str):
        """Parsa dati da JSON-LD."""
        try:
            data = json.loads(json_ld)
            event_obj = None

            if isinstance(data, dict):
                if "@graph" in data:
                    events = [x for x in data["@graph"] if x.get("@type") == "Event"]
                    if events:
                        event_obj = events[0]
                elif data.get("@type") == "Event":
                    event_obj = data
            elif isinstance(data, list):
                events = [x for x in data if x.get("@type") == "Event"]
                if events:
                    event_obj = events[0]

            if event_obj:
                # Immagini
                ld_images = event_obj.get("image")
                if ld_images:
                    if isinstance(ld_images, list):
                        item["image_urls"].extend(ld_images)
                    else:
                        item["image_urls"].append(ld_images)

                # Prezzo
                offers = event_obj.get("offers", {})
                if isinstance(offers, dict):
                    price = offers.get("price")
                    if price:
                        item["price"] = str(price)
                elif isinstance(offers, list) and offers:
                    price = offers[0].get("price")
                    if price:
                        item["price"] = str(price)

                # Date
                if not item.get("date_start"):
                    item["date_start"] = self.parse_date_iso(event_obj.get("startDate"))
                if not item.get("date_end"):
                    item["date_end"] = self.parse_date_iso(event_obj.get("endDate"))

        except Exception as e:
            self.logger.warning(f"Errore parsing JSON-LD: {e}")

    def _extract_event_info(self, response) -> dict:
        """Estrae informazioni evento dal widget HTML."""
        event_info = {}
        info_dls = response.xpath('//div[contains(@class, "c-widget_content")]/dl')

        for dl in info_dls:
            # Cerca chiave
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
