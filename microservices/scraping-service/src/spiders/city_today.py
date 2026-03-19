# -*- coding: utf-8 -*-
"""
Spider per la rete *Today.it - Eventi da 50+ città italiane.

La rete Today.it comprende siti come MilanoToday, RomaToday, BolognaToday, etc.
Ogni città ha un dominio dedicato con la stessa struttura HTML.

Utilizzo:
    # Scrapy diretto - singola città
    scrapy crawl city_today -a cities=milano -o output.json

    # Scrapy diretto - multiple città
    scrapy crawl city_today -a cities=milano,roma,bologna -o output.json

    # Con periodo specifico
    scrapy crawl city_today -a cities=milano -a periodo=weekend

    # Scrapyd
    curl http://localhost:6800/schedule.json \
        -d project=events_scraper \
        -d spider=city_today \
        -d cities=milano,roma \
        -d periodo=questa-settimana

Parametri:
    cities: Lista città separate da virgola (default: tutte)
    periodo: oggi, domani, weekend, questa-settimana, prossima-settimana, questo-mese
"""

import html as html_lib
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import scrapy
from scrapy import Selector

from spiders.base import BaseEventSpider
from spiders.utils import DEFAULT_CRAWL_SETTINGS


# =============================================================================
# CONFIGURAZIONE CITTÀ
# =============================================================================

CITIES: Dict[str, Dict[str, str]] = {
    # Nord
    "milano": {"domain": "www.milanotoday.it", "name": "Milano"},
    "torino": {"domain": "www.torinotoday.it", "name": "Torino"},
    "genova": {"domain": "www.genovatoday.it", "name": "Genova"},
    "venezia": {"domain": "www.veneziatoday.it", "name": "Venezia"},
    "bologna": {"domain": "www.bolognatoday.it", "name": "Bologna"},
    "verona": {"domain": "www.veronasera.it", "name": "Verona"},
    "treviso": {"domain": "www.trevisotoday.it", "name": "Treviso"},
    "trento": {"domain": "www.trentotoday.it", "name": "Trento"},
    "udine": {"domain": "www.udinetoday.it", "name": "Udine"},
    "pordenone": {"domain": "www.pordenonetoday.it", "name": "Pordenone"},
    "vicenza": {"domain": "www.vicenzatoday.it", "name": "Vicenza"},
    "padova": {"domain": "www.padovatoday.it", "name": "Padova"},
    "monza": {"domain": "www.monzatoday.it", "name": "Monza"},
    "lecco": {"domain": "www.leccotoday.it", "name": "Lecco"},
    "sondrio": {"domain": "www.sondriotoday.it", "name": "Sondrio"},
    "novara": {"domain": "www.novaratoday.it", "name": "Novara"},
    "brescia": {"domain": "www.bresciatoday.it", "name": "Brescia"},
    "parma": {"domain": "www.parmatoday.it", "name": "Parma"},
    "rimini": {"domain": "www.riminitoday.it", "name": "Rimini"},
    "ravenna": {"domain": "www.ravennatoday.it", "name": "Ravenna"},
    "forli": {"domain": "www.forlitoday.it", "name": "Forlì"},
    "cesena": {"domain": "www.cesenatoday.it", "name": "Cesena"},
    "como": {"domain": "www.quicomo.it", "name": "Como"},
    "piacenza": {"domain": "www.ilpiacenza.it", "name": "Piacenza"},
    "trieste": {"domain": "www.triesteprima.it", "name": "Trieste"},
    # Centro
    "roma": {"domain": "www.romatoday.it", "name": "Roma"},
    "firenze": {"domain": "www.firenzetoday.it", "name": "Firenze"},
    "pisa": {"domain": "www.pisatoday.it", "name": "Pisa"},
    "livorno": {"domain": "www.livornotoday.it", "name": "Livorno"},
    "perugia": {"domain": "www.perugiatoday.it", "name": "Perugia"},
    "terni": {"domain": "www.ternitoday.it", "name": "Terni"},
    "ancona": {"domain": "www.anconatoday.it", "name": "Ancona"},
    "latina": {"domain": "www.latinatoday.it", "name": "Latina"},
    "frosinone": {"domain": "www.frosinonetoday.it", "name": "Frosinone"},
    "viterbo": {"domain": "www.viterbotoday.it", "name": "Viterbo"},
    "arezzo": {"domain": "www.arezzonotizie.it", "name": "Arezzo"},
    "pescara": {"domain": "www.ilpescara.it", "name": "Pescara"},
    # Sud e Isole
    "napoli": {"domain": "www.napolitoday.it", "name": "Napoli"},
    "palermo": {"domain": "www.palermotoday.it", "name": "Palermo"},
    "catania": {"domain": "www.cataniatoday.it", "name": "Catania"},
    "messina": {"domain": "www.messinatoday.it", "name": "Messina"},
    "bari": {"domain": "www.baritoday.it", "name": "Bari"},
    "foggia": {"domain": "www.foggiatoday.it", "name": "Foggia"},
    "salerno": {"domain": "www.salernotoday.it", "name": "Salerno"},
    "avellino": {"domain": "www.avellinotoday.it", "name": "Avellino"},
    "reggio-calabria": {"domain": "www.reggiotoday.it", "name": "Reggio Calabria"},
    "lecce": {"domain": "www.lecceprima.it", "name": "Lecce"},
    "brindisi": {"domain": "www.brindisireport.it", "name": "Brindisi"},
    "agrigento": {"domain": "www.agrigentonotizie.it", "name": "Agrigento"},
    "caserta": {"domain": "www.casertanews.it", "name": "Caserta"},
}

# Periodi disponibili
PERIODI = ["oggi", "domani", "weekend", "questa-settimana", "prossima-settimana", "questo-mese"]


def get_date_range(periodo: str) -> Tuple[datetime, datetime]:
    """
    Calcola date inizio/fine per il periodo specificato.

    Args:
        periodo: Nome del periodo

    Returns:
        Tupla (data_inizio, data_fine)
    """
    today = datetime.now().date()

    if periodo == "oggi":
        return today, today
    elif periodo == "domani":
        tomorrow = today + timedelta(days=1)
        return tomorrow, tomorrow
    elif periodo == "weekend":
        days_until_saturday = (5 - today.weekday()) % 7
        if days_until_saturday == 0 and today.weekday() == 5:
            saturday = today
        else:
            saturday = today + timedelta(days=days_until_saturday)
        sunday = saturday + timedelta(days=1)
        return saturday, sunday
    elif periodo == "questa-settimana":
        days_until_sunday = 6 - today.weekday()
        sunday = today + timedelta(days=days_until_sunday)
        return today, sunday
    elif periodo == "prossima-settimana":
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        next_monday = today + timedelta(days=days_until_monday)
        next_sunday = next_monday + timedelta(days=6)
        return next_monday, next_sunday
    elif periodo == "questo-mese":
        first_day = today.replace(day=1)
        if today.month == 12:
            last_day = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            last_day = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        return first_day, last_day
    else:
        # Default: questa settimana
        days_until_sunday = 6 - today.weekday()
        sunday = today + timedelta(days=days_until_sunday)
        return today, sunday


class CityTodaySpider(BaseEventSpider):
    """
    Spider per la rete *Today.it.

    Supporta 50+ città italiane con la stessa struttura HTML.
    Può scrapare singole città o gruppi di città.
    """

    name = "city_today"
    source_name = "city_today"

    custom_settings = {
        **DEFAULT_CRAWL_SETTINGS,
        "DOWNLOAD_DELAY": 1,
    }

    def __init__(
        self,
        cities: str = None,
        periodo: str = "questa-settimana",
        *args,
        **kwargs,
    ):
        """
        Inizializza lo spider.

        Args:
            cities: Lista città separate da virgola (default: tutte)
            periodo: Periodo temporale per il filtro date
        """
        super().__init__(*args, **kwargs)

        # Parse lista città
        if cities is None:
            self.cities = list(CITIES.keys())
        else:
            self.cities = [c.strip().lower() for c in cities.split(",")]

        # Valida città
        for city in self.cities:
            if city not in CITIES:
                available = ", ".join(sorted(CITIES.keys()))
                raise ValueError(f"Città '{city}' non supportata. Disponibili: {available}")

        # Valida periodo
        self.periodo = periodo.lower() if periodo else "questa-settimana"
        if self.periodo not in PERIODI:
            raise ValueError(f"Periodo '{self.periodo}' non supportato. Disponibili: {', '.join(PERIODI)}")

        # Calcola date
        date_start, date_end = get_date_range(self.periodo)
        self.date_path = f"dal/{date_start.strftime('%Y-%m-%d')}/al/{date_end.strftime('%Y-%m-%d')}/"

        # Configura domini
        self.allowed_domains = [CITIES[city]["domain"] for city in self.cities]
        self.start_urls = [
            f"https://{CITIES[city]['domain']}/eventi/{self.date_path}"
            for city in self.cities
        ]

        self.logger.info(f"Città: {', '.join([CITIES[c]['name'] for c in self.cities])}")
        self.logger.info(f"Periodo: {self.periodo} ({date_start} - {date_end})")

    def _get_city_from_url(self, url: str) -> Optional[str]:
        """Estrae il nome della città dall'URL."""
        for city_key, city_info in CITIES.items():
            if city_info["domain"] in url:
                return city_info["name"]
        return None

    def _get_city_key_from_url(self, url: str) -> Optional[str]:
        """Estrae la chiave della città dall'URL."""
        for city_key, city_info in CITIES.items():
            if city_info["domain"] in url:
                return city_key
        return None

    def parse(self, response):
        """
        Parsa la pagina lista eventi.

        Args:
            response: Risposta HTTP della pagina lista
        """
        city_name = self._get_city_from_url(response.url)
        event_cards = response.css("article.c-card")
        seen_urls = set()

        for card in event_cards:
            # Dati dalla lista
            raw_list = self._extract_card_data(card)

            # Trova link evento
            all_links = card.css("a::attr(href)").getall()

            # Gestione contenuti lazy-loaded
            async_html = card.css('script[type="text/async-html"]::text').get()
            if async_html:
                decoded_html = html_lib.unescape(async_html)
                lazy_selector = Selector(text=decoded_html)
                if not all_links:
                    all_links = lazy_selector.css("a::attr(href)").getall()
                # Arricchisci dati da lazy-loaded
                raw_list = self._enrich_from_lazy(raw_list, lazy_selector)

            # Trova link evento valido
            event_link = None
            for link in all_links:
                if link and ".html" in link and "/eventi/" in link:
                    if "weekend" not in link and "/location/" not in link:
                        event_link = link
                        break

            if not event_link:
                continue

            full_url = response.urljoin(event_link)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            # Pulisci dati lista
            for key in raw_list:
                if isinstance(raw_list[key], str):
                    raw_list[key] = self.clean_text(raw_list[key])

            city_key = self._get_city_key_from_url(response.url)

            yield response.follow(
                event_link,
                callback=self.parse_event_detail,
                meta={
                    "raw_list": raw_list,
                    "url": full_url,
                    "city": city_name,
                    "city_key": city_key,
                },
            )

    def _extract_card_data(self, card) -> dict:
        """Estrae dati dalla card evento."""
        raw_list = {
            "image": None,
            "category": None,
            "title": None,
            "stars": None,
            "date": None,
            "location": None,
        }

        raw_list["title"] = card.xpath('.//*[contains(@class, "heading")]/text()').get()
        raw_list["category"] = card.xpath('.//*[contains(@class, "kicker")]/text()').get()
        raw_list["image"] = card.css("img::attr(src)").get()

        # Stelle/rating
        stars_count = len(card.css("svg.c-rating.c-rating--filled").getall())
        if stars_count > 0:
            raw_list["stars"] = stars_count

        # Data e location
        details_list = card.css("ul.c-card__list-details li.c-card__item-details")
        for detail_item in details_list:
            use_elem = detail_item.css("use")
            if use_elem:
                href_val = use_elem.xpath("@*").getall()
                href_str = " ".join(href_val) if href_val else ""

                if "calendar" in href_str:
                    raw_list["date"] = detail_item.css("span.u-label-07::text").get()
                elif "map-pin" in href_str:
                    raw_list["location"] = detail_item.css("span.u-label-07::text").get()

        return raw_list

    def _enrich_from_lazy(self, raw_list: dict, lazy_selector) -> dict:
        """Arricchisce dati da contenuto lazy-loaded."""
        if not raw_list["title"]:
            raw_list["title"] = (
                lazy_selector.css("img::attr(title)").get()
                or lazy_selector.css("img::attr(alt)").get()
            )
        if not raw_list["category"]:
            raw_list["category"] = lazy_selector.xpath('.//*[contains(@class, "kicker")]/text()').get()
        if not raw_list["image"]:
            raw_list["image"] = lazy_selector.css("img::attr(src)").get()

        # Date e location da lazy
        if not raw_list["date"] or not raw_list["location"]:
            lazy_details = lazy_selector.css("ul.c-card__list-details li.c-card__item-details")
            for detail_item in lazy_details:
                use_elem = detail_item.css("use")
                if use_elem:
                    href_val = use_elem.xpath("@*").getall()
                    href_str = " ".join(href_val) if href_val else ""

                    if "calendar" in href_str and not raw_list["date"]:
                        raw_list["date"] = detail_item.css("span.u-label-07::text").get()
                    elif "map-pin" in href_str and not raw_list["location"]:
                        raw_list["location"] = detail_item.css("span.u-label-07::text").get()

        return raw_list

    def parse_event_detail(self, response):
        """
        Parsa la pagina dettaglio evento.

        Produce un EventItem con struttura nested (data, meta)
        compatibile con puglia_culture e la pipeline BatchExport.
        """
        raw_list = response.meta["raw_list"]

        # Estrai dati dal dettaglio
        info_grid = response.css("div.l-grid.l-grid--square")
        if not info_grid:
            info_grid = response.css("section.l-entry__body")

        raw_detail = {
            "dove": self._extract_dove(response, info_grid),
            "quando": self._extract_quando(response, info_grid),
            "prezzo": self._extract_prezzo(response, info_grid),
            "altre_informazioni": self._extract_altre_info(response, info_grid),
            "descrizione": self._extract_descrizione(response),
            "image": response.css("figure.l-entry__media img::attr(src)").get()
            or response.xpath('//meta[@property="og:image"]/@content').get(),
        }

        # Titolo e categoria dal dettaglio
        title = self.clean_text(response.css("h1.l-entry__title::text").get()) or raw_list.get("title")
        category_detail = self.clean_text(
            response.css(".c-card__kicker::text").get()
            or response.xpath('//meta[@property="article:section"]/@content').get()
        )
        category_value = category_detail or raw_list.get("category")

        # Location
        dove = raw_detail.get("dove") or {}
        city_name = response.meta["city"]
        location_name = dove.get("name")

        # Date
        quando = raw_detail.get("quando") or {}
        date_start = quando.get("date_start")
        date_end = quando.get("date_end")

        # Prezzo e altre info
        price = raw_detail.get("prezzo")
        altre_info = raw_detail.get("altre_informazioni") or {}

        # Hash
        uuid = self.generate_uuid(title or "", date_start or "", location_name or "")
        content_hash = self.generate_content_hash(
            raw_detail.get("descrizione") or "", price or "", "",
        )

        # URL e slug
        url = response.meta["url"]
        url_path = url.rstrip("/")
        event_id = url_path.split("/")[-1].replace(".html", "")

        # Costruisci EventItem con struttura nested
        item = self.create_item(
            uuid=uuid,
            title=title,
            data={
                "description": raw_detail.get("descrizione"),
                "category": [category_value] if category_value else [],
                "image_url": raw_detail.get("image") or raw_list.get("image"),
                "dates": {
                    "date_start": date_start or "",
                    "date_end": date_end or "",
                    "date_display": raw_list.get("date") or "",
                },
                "city": {
                    "city_name": city_name,
                    "location_name": location_name,
                    "location_address": dove.get("address"),
                },
                "section": {
                    "price": price,
                    "website": altre_info.get("website"),
                    "quando_raw": quando.get("raw_text"),
                    "dove_raw": dove.get("raw_text"),
                    "altre_info_raw": altre_info.get("raw_text"),
                },
            },
            meta={
                "content_hash": content_hash,
                "url": url,
                "event_id": event_id,
                "category": category_value or "evento",
                "source": self.source_name,
                "city_key": response.meta.get("city_key"),
            },
        )

        yield item

    def _extract_dove(self, response, info_grid) -> dict:
        """Estrae sezione 'Dove'."""
        dove = {"raw_text": None, "name": None, "address": None}

        location_section = info_grid.xpath('.//span[contains(text(), "Dove")]/parent::div')
        if not location_section:
            location_section = response.xpath(
                '//span[contains(text(), "Dove")]/parent::div[contains(@class, "l-grid__item")]'
            )

        if location_section:
            # Escludi lo span label "Dove" dal testo raw
            raw_parts = location_section.xpath(".//*[not(self::span[contains(@class,'heading')] or self::span[text()='Dove'])]//text()").getall()
            if not raw_parts:
                raw_parts = location_section.xpath(".//p//text()").getall()
            dove["raw_text"] = self.clean_text(" ".join(raw_parts))
            dove["name"] = self.clean_text(location_section.css("a.o-link-primary::text").get())

            address = location_section.xpath('.//p//a[@href="#map"]/text()').get()
            if not address:
                address = location_section.xpath(".//p/a/text()").get()
            if not address:
                address = location_section.xpath(".//p/text()").get()
            dove["address"] = self.clean_text(address)

        return dove

    def _extract_quando(self, response, info_grid) -> dict:
        """Estrae sezione 'Quando' con orari."""
        quando = {"raw_text": None, "date_start": None, "date_end": None, "schedule": None}

        date_section = info_grid.xpath('.//span[contains(text(), "Quando")]/parent::div')
        if not date_section:
            date_section = response.xpath(
                '//span[contains(text(), "Quando")]/parent::div[contains(@class, "l-grid__item")]'
            )

        if date_section:
            date_text = date_section.xpath("string()").get()
            # Rimuovi label "Quando" dal raw_text
            raw_text = self.clean_text(date_text)
            if raw_text and raw_text.startswith("Quando"):
                raw_text = self.clean_text(raw_text[6:])
            quando["raw_text"] = raw_text

            if date_text:
                dates = self.extract_dates_from_text(date_text)

                # Estrai orari (es. "10:00 - 19:00", "ore 20:30", "H: 10:00")
                times = re.findall(r"(\d{1,2}:\d{2})", date_text)

                if len(dates) >= 1:
                    quando["date_start"] = dates[0]
                    # Appendi orario inizio alla data
                    if times:
                        quando["date_start"] = f"{dates[0]} {times[0]}"
                if len(dates) >= 2:
                    quando["date_end"] = dates[1]
                    # Appendi orario fine (secondo orario se esiste, altrimenti primo)
                    if len(times) >= 2:
                        quando["date_end"] = f"{dates[1]} {times[1]}"
                    elif times:
                        quando["date_end"] = f"{dates[1]} {times[0]}"
                elif quando["date_start"]:
                    quando["date_end"] = quando["date_start"]

            quando["schedule"] = self.clean_text(date_section.css("span.u-label-011::text").get())

        return quando

    def _extract_prezzo(self, response, info_grid) -> Optional[str]:
        """Estrae sezione 'Prezzo'."""
        price_section = info_grid.xpath('.//span[contains(text(), "Prezzo")]/parent::div')
        if not price_section:
            price_section = response.xpath(
                '//span[contains(text(), "Prezzo")]/parent::div[contains(@class, "l-grid__item")]'
            )

        if price_section:
            price = price_section.css("span.c-badge::text").get()
            if not price:
                price = price_section.css("span.u-label-011::text").get()
            if not price:
                price_text = price_section.xpath("string()").get()
                if price_text:
                    price_text = price_text.replace("Prezzo", "").strip()
                    if "gratis" in price_text.lower():
                        price = "Gratis"
                    elif "non disponibile" in price_text.lower():
                        price = "Prezzo non disponibile"
                    else:
                        price_match = re.search(r"€\s*[\d,]+", price_text)
                        if price_match:
                            price = price_match.group(0)
            return self.clean_text(price) if price else None

        return None

    def _extract_altre_info(self, response, info_grid) -> dict:
        """Estrae sezione 'Altre informazioni'."""
        altre_info = {"raw_text": None, "website": None}

        other_section = info_grid.xpath('.//span[contains(text(), "Altre informazioni")]/parent::div')
        if not other_section:
            other_section = response.xpath(
                '//span[contains(text(), "Altre informazioni")]/parent::div[contains(@class, "l-grid__item")]'
            )

        if other_section:
            raw_text = self.clean_text(other_section.xpath("string()").get())
            if raw_text and raw_text.startswith("Altre informazioni"):
                raw_text = self.clean_text(raw_text[18:])
            altre_info["raw_text"] = raw_text
            website = other_section.css("a::attr(href)").get()
            if website and website.startswith("http"):
                altre_info["website"] = website

        return altre_info

    # Tag HTML da preservare nella descrizione
    _ALLOWED_TAGS = {"p", "br", "strong", "em", "b", "i", "ul", "ol", "li", "a", "h2", "h3", "h4"}

    def _extract_descrizione(self, response) -> Optional[str]:
        """Estrae la descrizione pulendo l'HTML e mantenendo solo tag essenziali."""
        content = None

        description_div = response.css("div.c-entry[data-content--body]")
        if description_div:
            content = "".join(description_div.xpath("node()").getall())

        if not content:
            description_section = response.css("section.c-entry.l-entry__body")
            if description_section:
                content = "".join(description_section.xpath("node()").getall())

        if not content:
            any_content = response.css("[data-content--body]")
            if any_content:
                content = "".join(any_content.xpath("node()").getall())

        if not content:
            return None

        return self._sanitize_html(content)

    def _sanitize_html(self, html_content: str) -> Optional[str]:
        """
        Pulisce HTML mantenendo solo tag essenziali (p, br, strong, em, a, liste, heading).

        Rimuove: div, script, style, commenti, attributi data-*, class, slot pubblicitari.
        """
        # Rimuovi commenti HTML
        text = re.sub(r"<!--.*?-->", "", html_content, flags=re.DOTALL)
        # Rimuovi tag script e style con contenuto
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        # Rimuovi div con attributi data-move, slot, ads
        text = re.sub(r"<div[^>]*data-move[^>]*>.*?</div>\s*</div>\s*</div>", "", text, flags=re.DOTALL)
        text = re.sub(r'<div[^>]*class="slot[^"]*"[^>]*>.*?</div>', "", text, flags=re.DOTALL)

        # Rimuovi tag non consentiti ma mantieni il contenuto
        def _replace_tag(match: re.Match) -> str:
            tag_name = match.group(1).lower().split()[0]
            if tag_name.lstrip("/") in self._ALLOWED_TAGS:
                # Tag consentito: rimuovi tutti gli attributi tranne href (per <a>)
                if tag_name == "a":
                    href = re.search(r'href="([^"]*)"', match.group(0))
                    if href:
                        return f'<a href="{href.group(1)}">'
                    return "<a>"
                # Per tag di chiusura o tag senza attributi
                if tag_name.startswith("/"):
                    return f"<{tag_name}>"
                return f"<{tag_name}>"
            # Tag non consentito: rimuovi il tag, tieni il contenuto
            return ""

        text = re.sub(r"<(/?\w[^>]*)>", _replace_tag, text)

        # Pulisci righe vuote multiple
        text = re.sub(r"\n\s*\n+", "\n", text)
        text = text.strip()

        return text if text else None
