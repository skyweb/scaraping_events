# -*- coding: utf-8 -*-
"""
Spider per lovevda.it - Portale turistico della Valle d'Aosta.

Il sito usa Orchard CMS (ASP.NET) con paginazione server-side.

Utilizzo:
    scrapy crawl love_vda
    scrapy crawl love_vda -a max_pages=10

Parametri:
    max_pages: Numero massimo di pagine (default: 5, 10 eventi/pagina)
"""

import re

import scrapy

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS, parse_italian_date_time


class LoveVdaSpider(BaseEventSpider):
    name = "love_vda"
    source_name = "love_vda"
    allowed_domains = ["www.lovevda.it"]

    BASE_URL = "https://www.lovevda.it"
    LISTING_URL = "https://www.lovevda.it/it/eventi/ricerca-generale"

    custom_settings = {**DEFAULT_CRAWL_SETTINGS}

    def __init__(self, max_pages: str = "5", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)
        self._seen_urls: set[str] = set()

    def start_requests(self):
        yield scrapy.Request(self.LISTING_URL, callback=self._parse_listing, meta={"page": 1})

    def _parse_listing(self, response):
        links = response.css('a[href*="/it/banca-dati/"]::attr(href)').getall()
        new_count = 0
        for href in links:
            full_url = response.urljoin(href)
            if full_url in self._seen_urls:
                continue
            self._seen_urls.add(full_url)
            new_count += 1
            yield scrapy.Request(full_url, callback=self._parse_detail)

        page = response.meta["page"]
        self.logger.info(f"Pagina {page}: {new_count} nuovi eventi")

        has_next = response.css("li.page-item a.page-link[rel='next']::attr(href)").get()
        if has_next and page < self.max_pages:
            yield scrapy.Request(response.urljoin(has_next), callback=self._parse_listing, meta={"page": page + 1})

    def _parse_detail(self, response):
        title = self.clean_text(response.css("h1.page-title::text").get())
        if not title:
            title = self.clean_text(response.xpath('//meta[@property="og:title"]/@content').get())
        if not title:
            return

        # Descrizione dal container principale della scheda
        description = self.clean_text(
            response.css("div.scheda-vit.container .row .col-12").xpath("string()").get()
        )
        if not description:
            description = self.clean_text(
                response.css(".text-truncate-3").xpath("string()").get()
            )

        # Immagine principale da og:image
        image_url = response.xpath('//meta[@property="og:image"]/@content').get()

        # Gallery: tutte le immagini del carousel → section.gallery
        gallery = []
        for img in response.css("div.scheda-vit-gallery .img-wrapper img"):
            src = img.attrib.get("src", "")
            if src:
                full_src = f"{self.BASE_URL}{src}" if src.startswith("/") else src
                gallery.append(full_src)

        # Location: nome luogo dal p.heading
        location_name = self.clean_text(
            response.css("p.heading.left.grey.margin-bottom-null::text").get()
        )

        # Date: div dentro p.left.grey (es. "13 marzo 2026 - 22 marzo 2026")
        date_text = self.clean_text(
            response.css("p.left.grey.margin-bottom-null div::text").get()
        )
        date_start = None
        date_end = None
        if date_text:
            parts = re.split(r'\s*-\s+', date_text)
            if parts:
                date_start, _ = parse_italian_date_time(parts[0].strip())
            if len(parts) >= 2:
                date_end, _ = parse_italian_date_time(parts[-1].strip())

        if date_end == date_start:
            date_end = None

        # Città dalla lista risultati o dal breadcrumb
        city = self.clean_text(response.css("a.link-localita::text").get())

        # Orari e costi dall'accordion
        orari = self._extract_orari(response)

        # Contatti
        contatti = self._extract_contatti(response)

        uuid = self.generate_uuid(title, date_start or "", location_name or city or "")
        content_hash = self.generate_content_hash(description or "", "", "")

        yield self.create_item(
            uuid=uuid, title=title,
            data={
                "description": description,
                "category": [],
                "image_url": image_url,
                "dates": {
                    "date_start": date_start or "",
                    "date_end": date_end or "",
                    "date_display": date_text or "",
                },
                "city": {
                    "city_name": city,
                    "location_name": location_name,
                    "location_address": None,
                },
                "section": {
                    "orari": orari.get("orari"),
                    "orari_costi_raw": orari.get("raw"),
                    "contatti_nome": contatti.get("nome"),
                    "contatti_indirizzo": contatti.get("indirizzo"),
                    "website": contatti.get("website"),
                    "gallery": gallery or None,
                },
            },
            meta={
                "content_hash": content_hash,
                "url": response.url,
                "event_id": slug,
                "category": "evento",
                "source": self.source_name,
            },
        )

    def _extract_orari(self, response) -> dict:
        """Estrae orari e costi dall'accordion 'Orari e costi'."""
        result = {"orari": None, "raw": None}

        # Cerca l'accordion "Orari e costi"
        accordion = response.css("#accordionScheda .collapse-body .category-box.times")
        if accordion:
            # Orari come lista (es. "10:00 - 12:00", "14:00 - 18:00")
            orari_divs = accordion.css("div::text").getall()
            orari_list = [self.clean_text(o) for o in orari_divs if self.clean_text(o)]
            if orari_list:
                result["orari"] = " | ".join(orari_list)

        # Testo completo dell'accordion come fallback
        collapse_body = response.css("#accordionScheda .collapse-body")
        if collapse_body:
            result["raw"] = self.clean_text(collapse_body.xpath("string()").get())

        return result

    def _extract_contatti(self, response) -> dict:
        """Estrae contatti dalla sezione gallery-meta."""
        contatti = {"nome": None, "indirizzo": None, "website": None}

        # Sezione contatti: div.gallery-meta
        meta_section = response.css("div.gallery-meta")
        if not meta_section:
            return contatti

        # Nome organizzatore: primo div.emphasis
        nome = self.clean_text(meta_section.css("div.emphasis::text").get())
        if nome:
            contatti["nome"] = nome

        # Indirizzo: secondo row con indirizzo
        for row in meta_section.css("div.row.info"):
            emphasis = self.clean_text(row.css("div.emphasis::text").get())
            value = self.clean_text(row.css("div.col-md-8::text").get())
            if value and not emphasis:
                contatti["indirizzo"] = value
                break

        # Website: primo link esterno (non pdf, non /it/contatti/)
        for link in meta_section.css("div.info--icons a[href]"):
            href = link.attrib.get("href", "")
            if href.startswith("http") and "lovevda.it" not in href:
                contatti["website"] = href
                break

        return contatti
