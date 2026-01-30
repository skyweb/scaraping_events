import scrapy
import html as html_lib
import re
import hashlib
from datetime import datetime, timedelta
from scrapy import Selector
from events.items import EventItem

# Configurazione città supportate
CITIES = {
    # Nord
    "milano": {
        "domain": "www.milanotoday.it",
        "start_url": "https://www.milanotoday.it/eventi/",
        "name": "Milano"
    },
    "torino": {
        "domain": "www.torinotoday.it",
        "start_url": "https://www.torinotoday.it/eventi/",
        "name": "Torino"
    },
    "genova": {
        "domain": "www.genovatoday.it",
        "start_url": "https://www.genovatoday.it/eventi/",
        "name": "Genova"
    },
    "venezia": {
        "domain": "www.veneziatoday.it",
        "start_url": "https://www.veneziatoday.it/eventi/",
        "name": "Venezia"
    },
    "bologna": {
        "domain": "www.bolognatoday.it",
        "start_url": "https://www.bolognatoday.it/eventi/",
        "name": "Bologna"
    },
    "verona": {
        "domain": "www.veronasera.it",
        "start_url": "https://www.veronasera.it/eventi/",
        "name": "Verona"
    },
    "treviso": {
        "domain": "www.trevisotoday.it",
        "start_url": "https://www.trevisotoday.it/eventi/",
        "name": "Treviso"
    },
    "trento": {
        "domain": "www.trentotoday.it",
        "start_url": "https://www.trentotoday.it/eventi/",
        "name": "Trento"
    },
    "udine": {
        "domain": "www.udinetoday.it",
        "start_url": "https://www.udinetoday.it/eventi/",
        "name": "Udine"
    },
    "pordenone": {
        "domain": "www.pordenonetoday.it",
        "start_url": "https://www.pordenonetoday.it/eventi/",
        "name": "Pordenone"
    },
    "vicenza": {
        "domain": "www.vicenzatoday.it",
        "start_url": "https://www.vicenzatoday.it/eventi/",
        "name": "Vicenza"
    },
    "padova": {
        "domain": "www.padovatoday.it",
        "start_url": "https://www.padovatoday.it/eventi/",
        "name": "Padova"
    },
    "monza": {
        "domain": "www.monzatoday.it",
        "start_url": "https://www.monzatoday.it/eventi/",
        "name": "Monza"
    },
    "lecco": {
        "domain": "www.leccotoday.it",
        "start_url": "https://www.leccotoday.it/eventi/",
        "name": "Lecco"
    },
    "sondrio": {
        "domain": "www.sondriotoday.it",
        "start_url": "https://www.sondriotoday.it/eventi/",
        "name": "Sondrio"
    },
    "novara": {
        "domain": "www.novaratoday.it",
        "start_url": "https://www.novaratoday.it/eventi/",
        "name": "Novara"
    },
    "brescia": {
        "domain": "www.bresciatoday.it",
        "start_url": "https://www.bresciatoday.it/eventi/",
        "name": "Brescia"
    },
    "parma": {
        "domain": "www.parmatoday.it",
        "start_url": "https://www.parmatoday.it/eventi/",
        "name": "Parma"
    },
    "rimini": {
        "domain": "www.riminitoday.it",
        "start_url": "https://www.riminitoday.it/eventi/",
        "name": "Rimini"
    },
    "ravenna": {
        "domain": "www.ravennatoday.it",
        "start_url": "https://www.ravennatoday.it/eventi/",
        "name": "Ravenna"
    },
    "forli": {
        "domain": "www.forlitoday.it",
        "start_url": "https://www.forlitoday.it/eventi/",
        "name": "Forlì"
    },
    "cesena": {
        "domain": "www.cesenatoday.it",
        "start_url": "https://www.cesenatoday.it/eventi/",
        "name": "Cesena"
    },
    "como": {
        "domain": "www.quicomo.it",
        "start_url": "https://www.quicomo.it/eventi/",
        "name": "Como"
    },
    "piacenza": {
        "domain": "www.ilpiacenza.it",
        "start_url": "https://www.ilpiacenza.it/eventi/",
        "name": "Piacenza"
    },
    "trieste": {
        "domain": "www.triesteprima.it",
        "start_url": "https://www.triesteprima.it/eventi/",
        "name": "Trieste"
    },

    # Centro
    "roma": {
        "domain": "www.romatoday.it",
        "start_url": "https://www.romatoday.it/eventi/",
        "name": "Roma"
    },
    "firenze": {
        "domain": "www.firenzetoday.it",
        "start_url": "https://www.firenzetoday.it/eventi/",
        "name": "Firenze"
    },
    "pisa": {
        "domain": "www.pisatoday.it",
        "start_url": "https://www.pisatoday.it/eventi/",
        "name": "Pisa"
    },
    "livorno": {
        "domain": "www.livornotoday.it",
        "start_url": "https://www.livornotoday.it/eventi/",
        "name": "Livorno"
    },
    "perugia": {
        "domain": "www.perugiatoday.it",
        "start_url": "https://www.perugiatoday.it/eventi/",
        "name": "Perugia"
    },
    "terni": {
        "domain": "www.ternitoday.it",
        "start_url": "https://www.ternitoday.it/eventi/",
        "name": "Terni"
    },
    "ancona": {
        "domain": "www.anconatoday.it",
        "start_url": "https://www.anconatoday.it/eventi/",
        "name": "Ancona"
    },
    "latina": {
        "domain": "www.latinatoday.it",
        "start_url": "https://www.latinatoday.it/eventi/",
        "name": "Latina"
    },
    "frosinone": {
        "domain": "www.frosinonetoday.it",
        "start_url": "https://www.frosinonetoday.it/eventi/",
        "name": "Frosinone"
    },
    "viterbo": {
        "domain": "www.viterbotoday.it",
        "start_url": "https://www.viterbotoday.it/eventi/",
        "name": "Viterbo"
    },
    "arezzo": {
        "domain": "www.arezzonotizie.it",
        "start_url": "https://www.arezzonotizie.it/eventi/",
        "name": "Arezzo"
    },
    "pescara": {
        "domain": "www.ilpescara.it",
        "start_url": "https://www.ilpescara.it/eventi/",
        "name": "Pescara"
    },

    # Sud e Isole
    "napoli": {
        "domain": "www.napolitoday.it",
        "start_url": "https://www.napolitoday.it/eventi/",
        "name": "Napoli"
    },
    "palermo": {
        "domain": "www.palermotoday.it",
        "start_url": "https://www.palermotoday.it/eventi/",
        "name": "Palermo"
    },
    "catania": {
        "domain": "www.cataniatoday.it",
        "start_url": "https://www.cataniatoday.it/eventi/",
        "name": "Catania"
    },
    "messina": {
        "domain": "www.messinatoday.it",
        "start_url": "https://www.messinatoday.it/eventi/",
        "name": "Messina"
    },
    "bari": {
        "domain": "www.baritoday.it",
        "start_url": "https://www.baritoday.it/eventi/",
        "name": "Bari"
    },
    "foggia": {
        "domain": "www.foggiatoday.it",
        "start_url": "https://www.foggiatoday.it/eventi/",
        "name": "Foggia"
    },
    "salerno": {
        "domain": "www.salernotoday.it",
        "start_url": "https://www.salernotoday.it/eventi/",
        "name": "Salerno"
    },
    "avellino": {
        "domain": "www.avellinotoday.it",
        "start_url": "https://www.avellinotoday.it/eventi/",
        "name": "Avellino"
    },
    "reggio-calabria": {
        "domain": "www.reggiotoday.it",
        "start_url": "https://www.reggiotoday.it/eventi/",
        "name": "Reggio Calabria"
    },
    "lecce": {
        "domain": "www.lecceprima.it",
        "start_url": "https://www.lecceprima.it/eventi/",
        "name": "Lecce"
    },
    "brindisi": {
        "domain": "www.brindisireport.it",
        "start_url": "https://www.brindisireport.it/eventi/",
        "name": "Brindisi"
    },
    "agrigento": {
        "domain": "www.agrigentonotizie.it",
        "start_url": "https://www.agrigentonotizie.it/eventi/",
        "name": "Agrigento"
    },
    "caserta": {
        "domain": "www.casertanews.it",
        "start_url": "https://www.casertanews.it/eventi/",
        "name": "Caserta"
    },
}

# Periodi disponibili
PERIODI = ["oggi", "domani", "weekend", "questa-settimana", "prossima-settimana", "questo-mese"]


def get_date_range(periodo):
    """Calcola date inizio/fine per il periodo specificato"""
    today = datetime.now().date()

    if periodo == "oggi":
        return today, today
    elif periodo == "domani":
        tomorrow = today + timedelta(days=1)
        return tomorrow, tomorrow
    elif periodo == "weekend":
        # Prossimo sabato e domenica
        days_until_saturday = (5 - today.weekday()) % 7
        if days_until_saturday == 0 and today.weekday() == 5:
            saturday = today
        else:
            saturday = today + timedelta(days=days_until_saturday)
        sunday = saturday + timedelta(days=1)
        return saturday, sunday
    elif periodo == "questa-settimana":
        # Da oggi a domenica
        days_until_sunday = 6 - today.weekday()
        sunday = today + timedelta(days=days_until_sunday)
        return today, sunday
    elif periodo == "prossima-settimana":
        # Da lunedì prossimo a domenica prossima
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        next_monday = today + timedelta(days=days_until_monday)
        next_sunday = next_monday + timedelta(days=6)
        return next_monday, next_sunday
    elif periodo == "questo-mese":
        # Da primo a ultimo del mese corrente
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


class EventsSpider(scrapy.Spider):
    """
    Spider per estrarre gli eventi da *Today.it

    Utilizzo:
        # Tutte le città (default)
        scrapy crawl events -o eventi.json

        # Solo una città specifica
        scrapy crawl events -a city=milano -o eventi_milano.json
        scrapy crawl events -a city=roma -o eventi_roma.json

    Città supportate: milano, napoli, bologna, roma, firenze, venezia
    """

    name = "events"

    custom_settings = {
        "USER_AGENT": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "ROBOTSTXT_OBEY": True,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1,
    }

    def __init__(self, cities=None, periodo="questa-settimana", *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Accetta lista di città
        if cities is None:
            self.cities = list(CITIES.keys())
        elif isinstance(cities, str):
            self.cities = [cities.lower()]
        else:
            self.cities = [c.lower() for c in cities]

        # Valida le città
        for city in self.cities:
            if city not in CITIES:
                raise ValueError(f"Città '{city}' non supportata. Città disponibili: {', '.join(CITIES.keys())}")

        # Valida e imposta il periodo
        self.periodo = periodo.lower() if periodo else "questa-settimana"
        if self.periodo not in PERIODI:
            raise ValueError(f"Periodo '{self.periodo}' non supportato. Periodi disponibili: {', '.join(PERIODI)}")

        # Calcola date per il periodo
        date_start, date_end = get_date_range(self.periodo)
        date_path = f"dal/{date_start.strftime('%Y-%m-%d')}/al/{date_end.strftime('%Y-%m-%d')}/"

        # Configura domini e URL in base alle città selezionate e periodo
        self.allowed_domains = [CITIES[city]["domain"] for city in self.cities]
        self.start_urls = [
            f"https://{CITIES[city]['domain']}/eventi/{date_path}"
            for city in self.cities
        ]
        self.logger.info(f"Scraping città: {', '.join([CITIES[c]['name'] for c in self.cities])}")
        self.logger.info(f"Periodo: {self.periodo} ({date_start} - {date_end})")

    def _get_city_from_url(self, url):
        """Estrae il nome della città dall'URL"""
        for city_key, city_info in CITIES.items():
            if city_info["domain"] in url:
                return city_info["name"]
        return None

    def _get_city_key_from_url(self, url):
        """Estrae la chiave della città dall'URL"""
        for city_key, city_info in CITIES.items():
            if city_info["domain"] in url:
                return city_key
        return None

    def parse(self, response):
        """Parse la pagina principale degli eventi - estrae dati grezzi dalla lista"""
        city_name = self._get_city_from_url(response.url)
        event_cards = response.css("article.c-card")
        seen_urls = set()

        for card in event_cards:
            # Inizializza raw_data per dati dalla lista
            raw_list = {
                "image": None,
                "category": None,
                "title": None,
                "stars": None,
                "date": None,
                "location": None
            }

            all_links = card.css("a::attr(href)").getall()
            raw_list["title"] = card.xpath('.//*[contains(@class, "heading")]/text()').get()
            raw_list["category"] = card.xpath('.//*[contains(@class, "kicker")]/text()').get()
            raw_list["image"] = card.css("img::attr(src)").get()

            # Cerca stelle/rating (conta svg.c-rating.c-rating--filled)
            stars_count = len(card.css("svg.c-rating.c-rating--filled").getall())
            if stars_count > 0:
                raw_list["stars"] = stars_count

            # Cerca data e location nella card (ul.c-card__list-details)
            details_list = card.css("ul.c-card__list-details li.c-card__item-details")
            for detail_item in details_list:
                # Estrai l'attributo href dall'elemento use (può essere xlink:href)
                use_elem = detail_item.css("use")
                if use_elem:
                    # Prova a ottenere xlink:href o href
                    href_val = use_elem.xpath("@*").getall()
                    href_str = " ".join(href_val) if href_val else ""

                    if "calendar" in href_str:
                        date_text = detail_item.css("span.u-label-07::text").get()
                        raw_list["date"] = self._clean_text(date_text)
                    elif "map-pin" in href_str:
                        location_text = detail_item.css("span.u-label-07::text").get()
                        raw_list["location"] = self._clean_text(location_text)

            # Gestione contenuti lazy-loaded
            async_html = card.css('script[type="text/async-html"]::text').get()
            if async_html:
                decoded_html = html_lib.unescape(async_html)
                lazy_selector = Selector(text=decoded_html)
                if not all_links:
                    all_links = lazy_selector.css("a::attr(href)").getall()
                if not raw_list["title"]:
                    raw_list["title"] = (
                            lazy_selector.css("img::attr(title)").get()
                            or lazy_selector.css("img::attr(alt)").get()
                    )
                if not raw_list["category"]:
                    raw_list["category"] = lazy_selector.xpath('.//*[contains(@class, "kicker")]/text()').get()
                if not raw_list["image"]:
                    raw_list["image"] = lazy_selector.css("img::attr(src)").get()

                # Estrai date e location da lazy-loaded se non già trovati
                if not raw_list["date"] or not raw_list["location"]:
                    lazy_details = lazy_selector.css("ul.c-card__list-details li.c-card__item-details")
                    for detail_item in lazy_details:
                        use_elem = detail_item.css("use")
                        if use_elem:
                            href_val = use_elem.xpath("@*").getall()
                            href_str = " ".join(href_val) if href_val else ""

                            if "calendar" in href_str and not raw_list["date"]:
                                date_text = detail_item.css("span.u-label-07::text").get()
                                raw_list["date"] = self._clean_text(date_text)
                            elif "map-pin" in href_str and not raw_list["location"]:
                                location_text = detail_item.css("span.u-label-07::text").get()
                                raw_list["location"] = self._clean_text(location_text)

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

            # Pulisci i dati grezzi della lista
            for key in raw_list:
                if isinstance(raw_list[key], str):
                    raw_list[key] = self._clean_text(raw_list[key])

            # Ottieni city_key per lookup city_id
            city_key = self._get_city_key_from_url(response.url)

            yield response.follow(
                event_link,
                callback=self.parse_event_detail,
                meta={
                    "raw_list": raw_list,
                    "url": full_url,
                    "city": city_name,
                    "city_key": city_key,
                    "city_id": CITIES.get(city_key, {}).get("city_id") if city_key else None
                },
            )

    def parse_event_detail(self, response):
        """Parse la pagina di dettaglio dell'evento - estrae dati grezzi e mappa al JSON finale"""
        raw_list = response.meta["raw_list"]

        # Inizializza raw_data per dati dal dettaglio
        raw_detail = {
            "dove": None,
            "quando": None,
            "prezzo": None,
            "altre_informazioni": None,
            "descrizione": None,
            "image": None
        }

        # Cerca la griglia info
        info_grid = response.css("div.l-grid.l-grid--square")
        if not info_grid:
            info_grid = response.css("section.l-entry__body")

        # Estrai "Dove" (location completa)
        raw_detail["dove"] = self._extract_raw_dove(response, info_grid)

        # Estrai "Quando" (date e orari)
        raw_detail["quando"] = self._extract_raw_quando(response, info_grid)

        # Estrai "Prezzo"
        raw_detail["prezzo"] = self._extract_raw_prezzo(response, info_grid)

        # Estrai "Altre informazioni"
        raw_detail["altre_informazioni"] = self._extract_raw_altre_info(response, info_grid)

        # Estrai descrizione
        raw_detail["descrizione"] = self._extract_raw_descrizione(response)

        # Estrai immagine dal dettaglio
        image = response.css("figure.l-entry__media img::attr(src)").get()
        if not image:
            image = response.xpath('//meta[@property="og:image"]/@content').get()
        raw_detail["image"] = image

        # Estrai titolo dal dettaglio (più accurato)
        title_detail = response.css("h1.l-entry__title::text").get()
        if title_detail:
            title_detail = self._clean_text(title_detail)

        # Estrai categoria dal dettaglio
        category_detail = response.css(".c-card__kicker::text").get()
        if not category_detail:
            category_detail = response.xpath('//meta[@property="article:section"]/@content').get()
        if category_detail:
            category_detail = self._clean_text(category_detail)

        # Combina raw_data
        raw_data = {
            "list": raw_list,
            "detail": raw_detail
        }

        # Crea l'item e mappa i campi
        item = EventItem()

        # Dati grezzi completi
        item["raw_data"] = raw_data

        # Metadati Fonte
        item["source"] = "city_today"
        item["url"] = response.meta["url"]

        # Event ID: estrai dall'URL (parte finale senza .html)
        url_path = response.meta["url"].rstrip("/")
        event_id = url_path.split("/")[-1].replace(".html", "")
        item["event_id"] = event_id

        # Titolo: preferisci dettaglio, fallback a lista
        item["title"] = title_detail or raw_list.get("title")

        # Descrizione
        item["description"] = raw_detail.get("descrizione")

        # Categoria: converti in array (TEXT[])
        category_value = category_detail or raw_list.get("category")
        if category_value:
            item["category"] = [category_value]  # Array con singolo elemento
        else:
            item["category"] = []

        # Immagine: preferisci dettaglio, fallback a lista
        item["image_url"] = raw_detail.get("image") or raw_list.get("image")

        # Location
        dove = raw_detail.get("dove") or {}
        item["city"] = response.meta["city"]
        item["city_id"] = response.meta.get("city_id")  # FK a comuni_italiani.comuni.id
        item["location_name"] = dove.get("name")
        item["location_address"] = dove.get("address")

        # Dettagli
        item["price"] = raw_detail.get("prezzo")
        altre_info = raw_detail.get("altre_informazioni") or {}
        item["website"] = altre_info.get("website")

        # Date
        quando = raw_detail.get("quando") or {}
        item["date_start"] = quando.get("date_start")
        item["date_end"] = quando.get("date_end")
        item["date_display"] = raw_list.get("date")  # Testo leggibile dalla lista

        # Metadata
        item["scraped_at"] = datetime.now().isoformat()

        # Genera UUID dall'hash di titolo + data_start + location_name
        uuid_string = f"{item.get('title', '')}{item.get('date_start', '')}{item.get('location_name', '')}"
        item["uuid"] = hashlib.sha256(uuid_string.encode('utf-8')).hexdigest()[:16]

        # Genera content_hash dall'hash di descrizione
        content_string = f"{item.get('description', '')}"
        item["content_hash"] = hashlib.sha256(content_string.encode('utf-8')).hexdigest()[:16]

        # Incrementa contatore per città
        if item.get("city"):
            self.crawler.stats.inc_value(f"items_per_city/{item['city']}")

        yield item

    def _extract_raw_dove(self, response, info_grid):
        """Estrae dati grezzi della sezione 'Dove'"""
        dove = {
            "raw_text": None,
            "name": None,
            "address": None
        }

        location_section = info_grid.xpath('.//span[contains(text(), "Dove")]/parent::div')
        if not location_section:
            location_section = response.xpath(
                '//span[contains(text(), "Dove")]/parent::div[contains(@class, "l-grid__item")]'
            )

        if location_section:
            # Testo grezzo completo
            dove["raw_text"] = self._clean_text(location_section.xpath("string()").get())

            # Nome location
            name = location_section.css("a.o-link-primary::text").get()
            dove["name"] = self._clean_text(name)

            # Indirizzo
            address = location_section.xpath('.//p//a[@href="#map"]/text()').get()
            if not address:
                address = location_section.xpath(".//p/a/text()").get()
            if not address:
                address = location_section.xpath(".//p/text()").get()
            dove["address"] = self._clean_text(address)

        return dove

    def _extract_raw_quando(self, response, info_grid):
        """Estrae dati grezzi della sezione 'Quando'"""
        quando = {
            "raw_text": None,
            "date_start": None,
            "date_end": None,
            "schedule": None
        }

        date_section = info_grid.xpath('.//span[contains(text(), "Quando")]/parent::div')
        if not date_section:
            date_section = response.xpath(
                '//span[contains(text(), "Quando")]/parent::div[contains(@class, "l-grid__item")]'
            )

        if date_section:
            # Testo grezzo completo
            date_text = date_section.xpath("string()").get()
            quando["raw_text"] = self._clean_text(date_text)

            if date_text:
                # Estrai date DD/MM/YYYY
                date_matches = re.findall(r"(\d{2}/\d{2}/\d{4})", date_text)

                if len(date_matches) >= 1:
                    date_start = self._parse_date(date_matches[0])
                    if date_start:
                        quando["date_start"] = date_start.strftime("%Y-%m-%d")

                if len(date_matches) >= 2:
                    date_end = self._parse_date(date_matches[1])
                    if date_end:
                        quando["date_end"] = date_end.strftime("%Y-%m-%d")
                elif quando["date_start"]:
                    quando["date_end"] = quando["date_start"]

            # Schedule/orari
            schedule_text = date_section.css("span.u-label-011::text").get()
            quando["schedule"] = self._clean_text(schedule_text)

        return quando

    def _extract_raw_prezzo(self, response, info_grid):
        """Estrae dati grezzi della sezione 'Prezzo'"""
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
            return self._clean_text(price) if price else None

        return None

    def _extract_raw_altre_info(self, response, info_grid):
        """Estrae dati grezzi della sezione 'Altre informazioni'"""
        altre_info = {
            "raw_text": None,
            "website": None
        }

        other_info_section = info_grid.xpath(
            './/span[contains(text(), "Altre informazioni")]/parent::div'
        )
        if not other_info_section:
            other_info_section = response.xpath(
                '//span[contains(text(), "Altre informazioni")]/parent::div[contains(@class, "l-grid__item")]'
            )

        if other_info_section:
            altre_info["raw_text"] = self._clean_text(other_info_section.xpath("string()").get())

            website = other_info_section.css("a::attr(href)").get()
            if website and website.startswith("http"):
                altre_info["website"] = website

        return altre_info

    def _extract_raw_descrizione(self, response):
        """Estrae la descrizione grezza dell'evento"""
        paragraphs = []
        description_div = response.css("div.c-entry[data-content--body]")
        if description_div:
            paragraphs = description_div.xpath(".//p//text()").getall()
        if not paragraphs:
            description_section = response.css("section.c-entry.l-entry__body")
            if description_section:
                paragraphs = description_section.xpath(".//p//text()").getall()
        if not paragraphs:
            any_content = response.css("[data-content--body]")
            if any_content:
                paragraphs = any_content.xpath(".//p//text()").getall()

        if paragraphs:
            desc = " ".join([self._clean_text(p) for p in paragraphs if p and p.strip()])
            return desc if desc else None

        return None

    def _parse_date(self, date_str):
        """Converte DD/MM/YYYY in oggetto datetime"""
        try:
            return datetime.strptime(date_str, "%d/%m/%Y")
        except ValueError:
            return None

    def _clean_text(self, text):
        """Pulisce il testo da spazi extra e caratteri speciali"""
        if text:
            return " ".join(text.split()).strip()
        return None
