# -*- coding: utf-8 -*-
"""
Spider per zero.eu - Eventi culturali italiani.

Zero.eu è un portale di eventi culturali con API REST.
Lo spider usa prima l'API per ottenere i dati strutturati,
poi visita le pagine HTML per arricchire le informazioni.

Utilizzo:
    # Scrapy diretto
    scrapy crawl zero_eu -a city=milano -o output.json

    # Scrapyd
    curl http://localhost:6800/schedule.json \
        -d project=events_scraper \
        -d spider=zero_eu \
        -d city=roma

Parametri:
    city: Slug della città (default: milano)
          Valori: milano, roma, bologna, torino, firenze, venezia, napoli
"""

import scrapy
from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class ZeroEuSpider(BaseEventSpider):
    """
    Spider per zero.eu.

    Flusso:
    1. Scarica lista città dall'API per mappare slug -> ID
    2. Scarica eventi per la città selezionata
    3. Per ogni evento, visita la pagina HTML per dettagli aggiuntivi
    """

    name = "zero_eu"
    source_name = "zero_eu"
    allowed_domains = ["zero.eu"]

    custom_settings = {
        **DEFAULT_CRAWL_SETTINGS,
        "ROBOTSTXT_OBEY": False,  # API spesso bloccata da robots.txt
        "DOWNLOAD_DELAY": 0.5,
    }

    # Mapping di fallback città -> ID (se l'API non risponde)
    FALLBACK_CITY_IDS = {
        "milano": 2,
        "bologna": 13,
        "roma": 3,
        "torino": 12,
        "firenze": 14,
        "venezia": 15,
        "napoli": 16,
    }

    def __init__(self, city: str = "milano", *args, **kwargs):
        """
        Inizializza lo spider.

        Args:
            city: Slug della città da scrapare (default: milano)
        """
        super().__init__(*args, **kwargs)
        self.target_city_slug = city.lower()
        self.target_city_id = None
        self.cities_map = {}

    def start_requests(self):
        """Inizia scaricando la lista delle città."""
        yield scrapy.Request(
            url="https://zero.eu/api/wp/v2/citta?per_page=100",
            callback=self.parse_cities,
        )

    def parse_cities(self, response):
        """
        Parsa la lista delle città e avvia lo scraping degli eventi.

        Args:
            response: Risposta JSON con lista città
        """
        cities = response.json()

        # Costruisce mappa slug -> ID
        for city in cities:
            slug = city.get("slug")
            city_id = city.get("id")
            if slug and city_id:
                self.cities_map[slug] = city_id

        # Cerca la città target
        if self.target_city_slug in self.cities_map:
            self.target_city_id = self.cities_map[self.target_city_slug]
            self.logger.info(
                f"Città trovata: '{self.target_city_slug}' (ID: {self.target_city_id})"
            )
        elif self.target_city_slug in self.FALLBACK_CITY_IDS:
            # Usa ID di fallback
            self.target_city_id = self.FALLBACK_CITY_IDS[self.target_city_slug]
            self.logger.warning(
                f"Città '{self.target_city_slug}' non in API, uso fallback ID: {self.target_city_id}"
            )
        else:
            self.logger.error(
                f"Città '{self.target_city_slug}' non trovata. "
                f"Disponibili: {', '.join(self.cities_map.keys())}"
            )
            return

        # Avvia scraping eventi
        yield scrapy.Request(
            url=f"https://zero.eu/api/v2/events?per_page=100&citta={self.target_city_id}&_embed=true",
            callback=self.parse_events,
            meta={"page": 1},
        )

    def parse_events(self, response):
        """
        Parsa la lista degli eventi dall'API.

        Args:
            response: Risposta JSON con lista eventi
        """
        events = response.json()

        if not events:
            self.logger.info("Nessun altro evento trovato")
            return

        for event in events:
            yield from self._parse_event_data(event)

        # Gestione paginazione
        current_page = response.meta.get("page", 1)
        total_pages = int(response.headers.get("X-WP-TotalPages", 0))

        if current_page < total_pages:
            next_page = current_page + 1
            self.logger.info(f"Pagina {next_page}/{total_pages}")
            yield scrapy.Request(
                url=(
                    f"https://zero.eu/api/v2/events?per_page=100"
                    f"&citta={self.target_city_id}&page={next_page}&_embed=true"
                ),
                callback=self.parse_events,
                meta={"page": next_page},
            )

    def _parse_event_data(self, data: dict):
        """
        Estrae dati evento dall'API e visita la pagina per dettagli.

        Args:
            data: Dati evento dall'API

        Yields:
            Request per la pagina dettaglio o EventItem
        """
        item = self.create_item()

        # ID e URL
        item["event_id"] = str(data.get("id", ""))
        item["url"] = data.get("link")
        item["slug"] = data.get("slug")

        # Titolo
        title = data.get("name", {}).get("plain")
        item["title"] = self.clean_text(title)

        # Descrizione (preserva HTML originale)
        content = data.get("content", {}).get("rendered")
        item["description"] = content

        # Categoria
        cats = data.get("category", [])
        if cats:
            item["category"] = [c.strip() for cat in cats for c in cat.split(",")]

        # Immagine
        featured_media = data.get("featured_image", {})
        if featured_media and "sizes" in featured_media:
            sizes = featured_media["sizes"]
            if "full" in sizes:
                item["image_url"] = sizes["full"].get("source_url") or sizes["full"].get("file")
            elif "large" in sizes:
                item["image_url"] = sizes["large"].get("source_url") or sizes["large"].get("file")

        # Location
        item["city"] = self.target_city_slug.capitalize()
        item["location_name"] = data.get("venue_name")
        item["location_coords"] = data.get("venue_coords")
        item["location_address"] = data.get("venue_address")

        # Arricchisci da _embedded
        if "_embedded" in data and "venue" in data["_embedded"]:
            venue_list = data["_embedded"]["venue"]
            if venue_list:
                venue = venue_list[0]
                full_addr = venue.get("plain_address") or venue.get("address_full")
                if full_addr:
                    item["location_address"] = full_addr

        # Prezzo
        item["price"] = data.get("price")

        # Date
        item["date_start"] = self.parse_date_iso(data.get("start_date"))
        item["date_end"] = self.parse_date_iso(data.get("end_date"))
        item["date_display"] = data.get("date_string") or data.get("human_date")
        item["time_start"] = data.get("start_time")
        item["time_end"] = data.get("end_time")
        item["date_scope"] = data.get("date_scope")

        # Visita pagina per dettagli aggiuntivi
        if item["url"]:
            yield scrapy.Request(
                url=item["url"],
                callback=self.parse_event_page,
                meta={"item": item},
                headers={
                    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Cookie": "pll_language=it; wp-wpml_current_language=it",
                },
                dont_filter=True,
            )
        else:
            # Genera hash e yield item
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

    def parse_event_page(self, response):
        """
        Estrae dettagli aggiuntivi dalla pagina HTML dell'evento.

        Args:
            response: Risposta HTML della pagina evento
        """
        item = response.meta["item"]

        # Indirizzo completo dalla pagina
        address_parts = response.xpath('//p[contains(@class, "venue")]/text()').getall()
        full_address = " ".join([p.strip() for p in address_parts if p.strip()]).strip()
        if full_address:
            item["location_address"] = full_address.strip(" ,-")

        # Data formattata
        when_text = response.xpath(
            '''
            //div[contains(@class, "resume-detail")]
            /h2[contains(text(), "When") or contains(text(), "Quando")]
            /following-sibling::p/text()
            '''
        ).get()

        if not when_text:
            when_text = response.css(".single-page-header .date::text").get()

        if when_text:
            item["date_display"] = self.clean_text(when_text)

        # Genera hash finali
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
