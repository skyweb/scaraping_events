# -*- coding: utf-8 -*-
"""
Spider per visitmolise.eu - Portale turistico del Molise.

Liferay DXP con Vue.js SPA. API JSON con structureKey 1298382.

NOTA: il server Liferay restituisce body vuoto con il downloader Twisted di Scrapy.
Potrebbe richiedere Splash/Playwright per funzionare. Spider disattivato nel DAG.

Utilizzo:
    scrapy crawl visit_molise
    scrapy crawl visit_molise -a max_pages=3
"""

import json

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class VisitMoliseSpider(BaseEventSpider):
    name = "visit_molise"
    source_name = "visit_molise"
    allowed_domains = ["www.visitmolise.eu"]

    API_URL = "https://www.visitmolise.eu/eventi"
    PAGE_SIZE = 50
    IMAGES_BASE = "https://d2c19lwvk4iqpa.cloudfront.net"

    custom_settings = {
        **DEFAULT_CRAWL_SETTINGS,
        "ROBOTSTXT_OBEY": False,
        # Disabilita compressione HTTP — Liferay restituisce body vuoto con gzip attivo in Scrapy
        "COMPRESSION_ENABLED": False,
    }

    def __init__(self, max_pages: str = "3", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)

    def _build_api_url(self, page: int) -> str:
        json_params = (
            f'{{"keyword":"","structureKey":"1298382",'
            f'"page":{page},"pageSize":{self.PAGE_SIZE},'
            f'"p1":[],"p2":[],"p3":[],"d1":"","d2":""}}'
        )
        encoded = (json_params
            .replace("{", "%7B").replace("}", "%7D")
            .replace("[", "%5B").replace("]", "%5D")
            .replace('"', "%22").replace(",", "%2C").replace(":", "%3A"))
        return f"{self.API_URL}?p_p_id=Configurable&p_p_lifecycle=2&p_p_resource_id=json&_Configurable_jsonParams={encoded}"

    def start_requests(self):
        yield scrapy.Request(
            self._build_api_url(1),
            callback=self._parse_events,
            meta={"page": 1},
            headers={
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://www.visitmolise.eu/eventi",
                "Accept-Encoding": "identity",
            },
            dont_filter=True,
        )

    def _parse_events(self, response):
        page = response.meta["page"]
        self.logger.info(f"Response pagina {page}: status={response.status}, len={len(response.body)}")

        if not response.body:
            self.logger.warning(f"Body vuoto pagina {page}")
            return

        try:
            data = json.loads(response.body)
        except Exception as e:
            self.logger.error(f"JSON non valido pagina {page}: {e}")
            return

        docs = data.get("docs", [])
        total = data.get("metadata", {}).get("numFound", 0)
        self.logger.info(f"Pagina {page}: {len(docs)} eventi (totale: {total})")

        for doc in docs:
            content = doc.get("contentJSON") or {}
            if isinstance(content, str):
                content = json.loads(content)
            item = self._build_item(doc, content)
            if item:
                yield item

        # Paginazione
        if len(docs) >= self.PAGE_SIZE and page < self.max_pages:
            yield scrapy.Request(
                self._build_api_url(page + 1),
                callback=self._parse_events,
                meta={"page": page + 1},
                headers={
                    "Accept": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": "https://www.visitmolise.eu/eventi",
                    "Accept-Encoding": "identity",
                },
                dont_filter=True,
            )

    def _build_item(self, doc: dict, content: dict):
        title = self.clean_text(content.get("title") or doc.get("titleCurrentValue"))
        if not title:
            return None

        description = self.clean_html(content.get("previewDescription"))
        if not description:
            description = self.clean_html(content.get("description"))

        view_url = content.get("viewUrl", "")
        url = f"https://www.visitmolise.eu{view_url}" if view_url else ""

        dates = content.get("Date") or {}
        date_start = self.parse_date_iso(dates.get("dataInizio", ""))
        date_end = self.parse_date_iso(dates.get("dataFine", ""))

        preview_pic = content.get("previewPicture", "")
        image_url = f"{self.IMAGES_BASE}{preview_pic}" if preview_pic and preview_pic.startswith("/") else preview_pic or None

        categories = []
        for group in content.get("groupedCategories", []):
            for cat in group.get("categories", []):
                name = cat.get("name")
                if name:
                    categories.append(name)

        city = None
        for group in content.get("groupedCategories", []):
            if group.get("vocabularyName") == "GEOGRAFICA":
                for cat in group.get("categories", []):
                    city = cat.get("name")
                    break

        location_coords = None
        geo = content.get("geoRef")
        if isinstance(geo, dict) and geo.get("latitude"):
            location_coords = {"type": "Point", "coordinates": [float(geo["longitude"]), float(geo["latitude"])]}

        contacts = [v for v in [
            content.get("sitoWeb"),
            content.get("telefono"),
            content.get("email"),
        ] if v]

        if date_end == date_start:
            date_end = None

        uuid = self.generate_uuid(title, date_start or "", city or "")
        content_hash = self.generate_content_hash(description or "", "", "")

        return self.create_item(
            uuid=uuid, title=title,
            data={
                "description": description, "category": categories, "cover_url": image_url,
                "dates": {"date_start": date_start or "", "date_end": date_end or "", "date_display": ""},
                "city": {"city_name": city, "location_name": None, "location_address": None, "location_coords": location_coords},
                "contacts": contacts or None,
            },
        )
