# -*- coding: utf-8 -*-
"""
Spider per visitnaples.eu - Portale turistico di Napoli.

Il sito usa un CMS custom (marketing-italia.eu) con API JSON proprietarie.
I contenuti sono articoli editoriali organizzati per categoria; gli eventi
non hanno campi strutturati per date/luogo/prezzo — questi dati sono
embedded nel testo HTML dei paragrafi.

Utilizzo:
    scrapy crawl visit_naples
    scrapy crawl visit_naples -a max_pages=5

Parametri:
    max_pages: Numero massimo di pagine da scansionare (default: 5, 12 articoli/pagina)
"""

import re
from typing import Optional

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


class VisitNaplesSpider(BaseEventSpider):
    """
    Spider API-based per visitnaples.eu (CMS marketing-italia.eu).

    Strategia:
    1. POST a API listing per ottenere gli articoli della categoria "Scopri Napoli" (id=60)
    2. Per ogni articolo, POST a API dettaglio per body HTML completo
    3. Estrae titolo, descrizione e immagine dall'API; date/luoghi dal testo (best-effort)
    """

    name = "visit_naples"
    source_name = "visit_naples"
    allowed_domains = ["visitnaples.eu", "visit.marketing-italia.eu", "images.marketing-italia.eu"]

    API_BASE = "https://visit.marketing-italia.eu/controller"
    API_LISTING = f"{API_BASE}/categorie.controller.php?act=ArticoliFiltrati"
    API_DETAIL = f"{API_BASE}/articoli.controller.php?act=DettaglioArticolo"
    IMAGES_BASE = "https://images.marketing-italia.eu/uploads/visitnaples/uploads_articoli/evidenza"

    # Categorie con contenuti eventi
    CATEGORIES = [
        {"id": "60", "slug": "scopri-napoli", "madre": "napoletanita"},
        {"id": "92", "slug": "eventi", "madre": "eventi"},
    ]

    custom_settings = {**DEFAULT_CRAWL_SETTINGS}

    def __init__(self, max_pages: str = "5", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)

    def start_requests(self):
        """Avvia il listing dalla pagina 1 per ogni categoria."""
        for cat in self.CATEGORIES:
            yield from self._request_listing(cat, 1)

    def _request_listing(self, cat: dict, page: int):
        """Genera richiesta POST all'API listing."""
        if page > self.max_pages:
            return

        yield scrapy.FormRequest(
            self.API_LISTING,
            formdata={
                "c_visit": "visitnaples",
                "lingua": "ita",
                "id_categoria": cat["id"],
                "categoria": cat["slug"],
                "paginazione": str(page),
            },
            callback=self._parse_listing,
            meta={"page": page, "category": cat},
        )

    def _parse_listing(self, response):
        """Parsa la risposta API listing."""
        try:
            data = response.json()
        except Exception:
            self.logger.error(f"Risposta API listing non valida")
            return

        articles = data.get("articoli", [])
        page = response.meta["page"]
        cat = response.meta["category"]

        if not articles:
            self.logger.info(f"[{cat['slug']}] Pagina {page}: nessun articolo, stop.")
            return

        self.logger.info(f"[{cat['slug']}] Pagina {page}: {len(articles)} articoli")

        for article in articles:
            slug = article.get("link_rewriting_articoli", "")
            if not slug:
                continue

            yield scrapy.FormRequest(
                self.API_DETAIL,
                formdata={
                    "c_visit": "visitnaples",
                    "lingua": "ita",
                    "id_articolo": slug,
                    "titolo": slug,
                },
                callback=self._parse_detail,
                meta={
                    "article_listing": article,
                    "category": cat,
                },
            )

        # Paginazione
        if page < self.max_pages:
            yield from self._request_listing(cat, page + 1)

    def _parse_detail(self, response):
        """Parsa la risposta API dettaglio articolo."""
        try:
            data = response.json()
        except Exception:
            self.logger.warning("Risposta API dettaglio non valida")
            return

        articles = data.get("articolo", [])
        if not articles:
            return
        article = articles[0]
        listing_data = response.meta["article_listing"]
        cat = response.meta["category"]

        title = self.clean_text(article.get("nome"))
        if not title:
            return

        # Descrizione dai paragrafi
        paragraphs = data.get("paragrafi", {}).get("paragrafo", [])
        description_parts = []
        for par in paragraphs:
            text = self.clean_html(par.get("testo_par", ""))
            if text:
                description_parts.append(text)
        description = " ".join(description_parts) if description_parts else None

        # Descrizione breve (meta)
        if not description:
            description = self.clean_text(article.get("meta_description"))

        # Immagine
        foto = article.get("foto") or listing_data.get("foto")
        image_url = f"{self.IMAGES_BASE}/{foto}" if foto else None

        # Data pubblicazione (DD/MM/YYYY)
        date_pub = article.get("data_pubblicazione", "")
        date_start = self.parse_date_dmy(date_pub)

        # Best-effort: estrai date dal testo dei paragrafi
        dates_from_text = self._extract_dates_from_paragraphs(paragraphs)
        if dates_from_text.get("date_start"):
            date_start = dates_from_text["date_start"]
        date_end = dates_from_text.get("date_end")

        if date_end == date_start:
            date_end = None

        # URL articolo
        madre = listing_data.get("link_rewriting_madre", cat["madre"])
        sotto = listing_data.get("link_rewriting_sotto", cat["slug"])
        slug = listing_data.get("link_rewriting_articoli", "")
        url = f"https://www.visitnaples.eu/{madre}/{sotto}/{slug}"

        # Slug
        event_slug = slug or self.slug_from_url(url)

        # Hash
        uuid = self.generate_uuid(title, date_start or "", "Napoli")
        content_hash = self.generate_content_hash(description or "", "", "")

        item = self.create_item(
            uuid=uuid,
            title=title,
            data={
                "description": description,
                "category": [cat["slug"]],
                "image_url": image_url,
                "dates": {
                    "date_start": date_start or "",
                    "date_end": date_end or "",
                    "date_display": "",
                },
                "city": {
                    "city_name": "Napoli",
                    "location_name": None,
                    "location_address": None,
                },
                "section": {},
            },
            meta={
                "content_hash": content_hash,
                "url": url,
                "slug": event_slug,
                "event_id": article.get("id_articolo", event_slug),
                "category": cat["slug"],
                "source": self.source_name,
            },
        )

        yield item

    def _extract_dates_from_paragraphs(self, paragraphs: list) -> dict:
        """Best-effort: cerca date DD/MM/YYYY nel testo HTML dei paragrafi."""
        result: dict[str, Optional[str]] = {"date_start": None, "date_end": None}

        all_text = " ".join(
            self.clean_html(p.get("testo_par", "")) or "" for p in paragraphs
        )

        dates = self.extract_dates_from_text(all_text)
        if dates:
            result["date_start"] = dates[0]
        if len(dates) >= 2:
            result["date_end"] = dates[-1]

        return result
