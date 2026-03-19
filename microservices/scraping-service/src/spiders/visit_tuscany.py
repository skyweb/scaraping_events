# -*- coding: utf-8 -*-
"""
Spider per visittuscany.com - Portale turistico della Toscana.

Il sito espone un endpoint GraphQL pubblico con tutti gli eventi.
Nessun scraping HTML necessario.

Utilizzo:
    scrapy crawl visit_tuscany
    scrapy crawl visit_tuscany -a max_pages=15
"""

import json

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class VisitTuscanySpider(BaseEventSpider):
    name = "visit_tuscany"
    source_name = "visit_tuscany"
    allowed_domains = ["www.visittuscany.com"]

    GRAPHQL_URL = "https://www.visittuscany.com/graphql"
    QUERY = """{
  allAssets(locale:"it", page:%d, config:"agg_evento_turismo") {
    totalCount
    pagination { current total rows }
    assets {
      id type href title
      img { src alt }
      ... on Event { when where info { icon text } }
    }
  }
}"""

    custom_settings = {**DEFAULT_CRAWL_SETTINGS}

    def __init__(self, max_pages: str = "15", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)

    def start_requests(self):
        yield self._graphql_request(1)

    def _graphql_request(self, page: int):
        return scrapy.Request(
            self.GRAPHQL_URL, method="POST",
            body=json.dumps({"query": self.QUERY % page}),
            headers={"Content-Type": "application/json"},
            callback=self._parse_events, meta={"page": page},
        )

    def _parse_events(self, response):
        try:
            body = response.json()
            data = body.get("data", {}) if isinstance(body, dict) else {}
            all_assets = data.get("allAssets", {}) if isinstance(data, dict) else {}
        except Exception as e:
            self.logger.error(f"Risposta GraphQL non valida: {e}")
            return

        if isinstance(all_assets, str):
            self.logger.error(f"allAssets è una stringa: {all_assets[:200]}")
            return

        assets = all_assets.get("assets", []) if isinstance(all_assets, dict) else []
        pagination = all_assets.get("pagination", {}) if isinstance(all_assets, dict) else {}
        page = response.meta["page"]
        total_pages = pagination.get("total", 1)

        self.logger.info(f"Pagina {page}/{total_pages}: {len(assets)} eventi")

        for asset in assets:
            item = self._build_item(asset)
            if item:
                yield item

        if page < min(self.max_pages, total_pages):
            yield self._graphql_request(page + 1)

    def _build_item(self, asset: dict):
        title = self.clean_text(asset.get("title"))
        if not title:
            return None

        href = asset.get("href", "")
        url = f"https://www.visittuscany.com{href}" if href.startswith("/") else href

        # Date dal campo "when" (es. "Dal 19 mar 2026 al 22 mar 2026")
        when = self.clean_text(asset.get("when"))
        where = self.clean_text(asset.get("where"))
        # Rimuovi "a " dal where (es. "a Sansepolcro" → "Sansepolcro")
        city = where.lstrip("a ").strip() if where else None

        # Immagine
        img = asset.get("img")
        image_url = img.get("src") if isinstance(img, dict) else (img if isinstance(img, str) else None)

        # Info extra (orari, prezzo, ecc.)
        section = {}
        for info in asset.get("info") or []:
            if not isinstance(info, dict):
                continue
            text = self.clean_text(info.get("text"))
            if text:
                icon = info.get("icon", "")
                if "clock" in icon or "time" in icon:
                    section["orari"] = text
                elif "euro" in icon or "price" in icon:
                    section["price"] = text
                else:
                    section.setdefault("extra", []).append(text)

        slug = self.slug_from_url(url)
        uuid = self.generate_uuid(title, when or "", city or "")
        content_hash = self.generate_content_hash("", "", "")

        return self.create_item(
            uuid=uuid, title=title,
            data={
                "description": None, "category": [], "image_url": image_url,
                "dates": {"date_start": "", "date_end": "", "date_display": when or ""},
                "city": {"city_name": city, "location_name": None, "location_address": None},
                "section": section,
            },
            meta={"content_hash": content_hash, "url": url, "slug": slug, "event_id": str(asset.get("id", slug)), "category": "evento", "source": self.source_name},
        )
