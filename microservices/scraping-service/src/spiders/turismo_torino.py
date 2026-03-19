# -*- coding: utf-8 -*-
"""
Spider per turismotorino.org - Portale turistico di Torino.

Il sito usa un CMS Directus con frontend Nuxt.js. Espone due API pubbliche:
- MeiliSearch per listing paginato degli eventi
- Directus REST per dettaglio completo con relazioni

Lo spider usa MeiliSearch per il listing e Directus per il dettaglio,
senza necessità di scraping HTML.

Utilizzo:
    scrapy crawl turismo_torino
    scrapy crawl turismo_torino -a max_pages=10

Parametri:
    max_pages: Numero massimo di pagine da scansionare (default: 5, 10 eventi/pagina)
"""

import json
import re

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class TurismoTorinoSpider(BaseEventSpider):
    """
    Spider API-based per turismotorino.org.

    Strategia:
    1. POST a MeiliSearch API per listing paginato (titolo, categoria, luogo, date)
    2. Per ogni evento, GET a Directus API per dettaglio completo (body, contatti, geo)
    """

    name = "turismo_torino"
    source_name = "turismo_torino"
    allowed_domains = ["turismotorino.org", "cms2.turismotorino.org"]

    SEARCH_URL = "https://cms2.turismotorino.org/search/ttp-frontend-it/meilimodule/lista"
    DIRECTUS_URL = "https://cms2.turismotorino.org/items/eventi"
    ASSETS_URL = "https://cms2.turismotorino.org/assets"

    # Campi Directus da richiedere per il dettaglio
    DIRECTUS_FIELDS = ",".join([
        "id", "nome", "status", "cover", "indirizzo",
        "geolocalizzazione", "scaduto",
        "translations.titolo", "translations.slug", "translations.body",
        "translations.languages_code", "translations.og_title", "translations.og_description",
        "date.data_inizio", "date.data_fine", "date.ricorrenza", "date.tutto_il_giorno",
        "categorie.categorie_id.translations.nome",
        "tipologie.tipologie_eventi_id.translations.nome",
        "contatti_email", "contatti_telefono",
        "comune.translations.nome",
        "tariffe.translations.nome", "tariffe.translations.descrizione",
    ])

    custom_settings = {**DEFAULT_CRAWL_SETTINGS, "ROBOTSTXT_OBEY": False}

    def __init__(self, max_pages: str = "5", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)

    def start_requests(self):
        """Avvia il listing dalla pagina 1 con MeiliSearch."""
        yield from self._request_search_page(1)

    def _request_search_page(self, page: int):
        """Genera richiesta POST a MeiliSearch."""
        if page > self.max_pages:
            return

        payload = {
            "sort": "data_inizio:asc",
            "tags": [],
            "limit": None,
            "query": "",
            "indice": "generale",
            "oggetti": ["eventi"],
            "targets": [],
            "tipologie_eventi": [],
            "tipologie_risorse": [],
            "switch_da_fare_vedere": 0,
            "switch_in_primo_piano": 0,
            "switch_nascondi_conclusi": 1,
            "page": page,
        }

        yield scrapy.Request(
            self.SEARCH_URL,
            method="POST",
            body=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            callback=self._parse_search,
            meta={"page": page},
        )

    def _parse_search(self, response):
        """Parsa la risposta MeiliSearch e richiede i dettagli Directus."""
        try:
            data = response.json()
        except Exception:
            self.logger.error(f"Risposta MeiliSearch non valida a pagina {response.meta['page']}")
            return

        hits = data.get("hits", [])
        if not hits:
            self.logger.info(f"Nessun evento a pagina {response.meta['page']}, stop.")
            return

        total_pages = data.get("totalPages", 1)
        self.logger.info(
            f"Pagina {response.meta['page']}/{total_pages}: {len(hits)} eventi"
        )

        for hit in hits:
            # Costruisci item direttamente dal search hit (Directus restituisce 403)
            item = self._build_from_hit(hit)
            if item:
                yield item

        # Paginazione
        page = response.meta["page"]
        if page < min(self.max_pages, total_pages):
            yield from self._request_search_page(page + 1)

    def _build_from_hit(self, hit: dict):
        """Costruisce EventItem dal search hit MeiliSearch (senza Directus)."""
        title = self.clean_text(hit.get("titolo"))
        if not title:
            return None

        description = self.clean_text(hit.get("descrizione"))
        city = self.clean_text(hit.get("luogo"))
        date_display = hit.get("ricorrenza", "")
        categories = hit.get("categoria", [])
        tipologie = hit.get("tipologia", [])

        # Immagine dal cover
        cover = hit.get("cover") or {}
        cover_id = cover.get("id") if isinstance(cover, dict) else cover
        image_url = f"{self.ASSETS_URL}/{cover_id}" if cover_id else None

        # Link
        link = hit.get("link", "")
        slug = link.strip("/").split("/")[-1] if link else ""

        uuid = self.generate_uuid(title, date_display or "", city or "")
        content_hash = self.generate_content_hash(description or "", "", "")

        return self.create_item(
            uuid=uuid, title=title,
            data={
                "description": description,
                "category": categories if isinstance(categories, list) else [categories] if categories else [],
                "image_url": image_url,
                "dates": {"date_start": "", "date_end": "", "date_display": date_display},
                "city": {"city_name": city, "location_name": None, "location_address": None},
                "section": {"tipologie": tipologie or None},
            },
            meta={
                "content_hash": content_hash,
                "url": f"https://turismotorino.org{link}" if link else "",
                "slug": slug,
                "event_id": hit.get("id", slug),
                "category": categories[0] if isinstance(categories, list) and categories else "evento",
                "source": self.source_name,
            },
        )
