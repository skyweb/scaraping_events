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

# Mapping giorni italiano -> numero
WEEKDAYS_IT = {
    "lunedì": 0, "martedì": 1, "mercoledì": 2, "giovedì": 3,
    "venerdì": 4, "sabato": 5, "domenica": 6
}

WEEKDAYS_IT_NAMES = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]

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
        """Estrae la città dall'URL"""
        for city_key, city_info in CITIES.items():
            if city_info["domain"] in url:
                return city_info["name"]
        return None

    def parse(self, response):
        """Parse la pagina principale degli eventi"""
        city_name = self._get_city_from_url(response.url)
        event_cards = response.css("article.c-card")
        seen_urls = set()

        for card in event_cards:
            all_links = card.css("a::attr(href)").getall()
            title = card.xpath('.//*[contains(@class, "heading")]/text()').get()
            category = card.xpath('.//*[contains(@class, "kicker")]/text()').get()
            image_url = card.css("img::attr(src)").get()

            if not all_links or not image_url:
                async_html = card.css('script[type="text/async-html"]::text').get()
                if async_html:
                    decoded_html = html_lib.unescape(async_html)
                    lazy_selector = Selector(text=decoded_html)
                    if not all_links:
                        all_links = lazy_selector.css("a::attr(href)").getall()
                    if not title:
                        title = (
                                lazy_selector.css("img::attr(title)").get()
                                or lazy_selector.css("img::attr(alt)").get()
                        )
                    if not category:
                        category = lazy_selector.xpath('.//*[contains(@class, "kicker")]/text()').get()
                    if not image_url:
                        image_url = lazy_selector.css("img::attr(src)").get()

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

            item = EventItem()
            item["url"] = full_url
            item["title"] = self._clean_text(title)
            item["category"] = self._clean_text(category)
            item["image_url"] = image_url
            item["city"] = city_name
            item["scraped_at"] = datetime.now().isoformat()

            yield response.follow(
                event_link,
                callback=self.parse_event_detail,
                meta={"item": item},
            )

    def parse_event_detail(self, response):
        """Parse la pagina di dettaglio dell'evento"""
        item = response.meta["item"]

        # Titolo
        title = response.css("h1.l-entry__title::text").get()
        if title:
            item["title"] = self._clean_text(title)

        # Categoria
        if not item.get("category"):
            category = response.css(".c-card__kicker::text").get()
            if not category:
                category = response.xpath('//meta[@property="article:section"]/@content').get()
            item["category"] = self._clean_text(category)

        # Immagine
        if not item.get("image_url"):
            image = response.css("figure.l-entry__media img::attr(src)").get()
            if not image:
                image = response.xpath('//meta[@property="og:image"]/@content').get()
            item["image_url"] = image

        # Cerca la griglia info
        info_grid = response.css("div.l-grid.l-grid--square")
        if not info_grid:
            info_grid = response.css("section.l-entry__body")

        # Location
        self._extract_location(response, info_grid, item)

        # Prezzo
        self._extract_price(response, info_grid, item)

        # Descrizione
        self._extract_description(response, item)

        # Sito web
        self._extract_website(response, info_grid, item)

        # Date e orari (genera array di date)
        self._extract_dates(response, info_grid, item)

        # Genera UUID dall'hash di titolo + data_start + location_name
        uuid_string = f"{item.get('title', '')}{item.get('date_start', '')}{item.get('location_name', '')}"
        item["uuid"] = hashlib.sha256(uuid_string.encode('utf-8')).hexdigest()[:16]

        # Genera content_hash dall'hash di descrizione + prezzo + ora
        content_string = f"{item.get('description', '')}{item.get('price', '')}{item.get('time_info', '')}"
        item["content_hash"] = hashlib.sha256(content_string.encode('utf-8')).hexdigest()[:16]

        # Incrementa contatore per città
        if item.get("city"):
            self.crawler.stats.inc_value(f"items_per_city/{item['city']}")

        yield item

    def _extract_location(self, response, info_grid, item):
        """Estrae informazioni sulla location"""
        location_section = info_grid.xpath('.//span[contains(text(), "Dove")]/parent::div')
        if not location_section:
            location_section = response.xpath(
                '//span[contains(text(), "Dove")]/parent::div[contains(@class, "l-grid__item")]'
            )
        if location_section:
            item["location_name"] = self._clean_text(
                location_section.css("a.o-link-primary::text").get()
            )
            address = location_section.xpath('.//p//a[@href="#map"]/text()').get()
            if not address:
                address = location_section.xpath(".//p/a/text()").get()
            if not address:
                address = location_section.xpath(".//p/text()").get()
            item["location_address"] = self._clean_text(address)

    def _extract_dates(self, response, info_grid, item):
        """Estrae le date e genera array di giorni con orari"""
        date_section = info_grid.xpath('.//span[contains(text(), "Quando")]/parent::div')
        if not date_section:
            date_section = response.xpath(
                '//span[contains(text(), "Quando")]/parent::div[contains(@class, "l-grid__item")]'
            )

        if not date_section:
            item["dates"] = []
            return

        date_text = date_section.xpath("string()").get()
        if not date_text:
            item["dates"] = []
            return

        # Estrai date DD/MM/YYYY
        date_matches = re.findall(r"(\d{2}/\d{2}/\d{4})", date_text)
        date_start = None
        date_end = None

        if len(date_matches) >= 1:
            date_start = self._parse_date(date_matches[0])
        if len(date_matches) >= 2:
            date_end = self._parse_date(date_matches[1])
        elif date_start:
            date_end = date_start

        if not date_start:
            item["dates"] = []
            return

        # Salva date originali in formato YYYY-MM-DD
        item["date_start"] = date_start.strftime("%Y-%m-%d")
        item["date_end"] = date_end.strftime("%Y-%m-%d")

        # Estrai il testo dello schedule (orari dettagliati)
        schedule_text = date_section.css("span.u-label-011::text").get()
        schedule_text = self._clean_text(schedule_text) if schedule_text else ""

        # Salva schedule originale se contiene giorni
        if schedule_text and any(day.lower() in schedule_text.lower() for day in WEEKDAYS_IT_NAMES):
            item["schedule"] = schedule_text

        # Trova i giorni della settimana specificati
        allowed_weekdays = self._extract_weekdays(date_text + " " + schedule_text)

        # Salva weekdays
        if allowed_weekdays:
            item["weekdays"] = ", ".join(allowed_weekdays)

        # Estrai orari per giorno
        day_times = self._parse_schedule(schedule_text)

        # Estrai orario sintetico
        time_match = re.search(r"(\d{1,2}[.:]\d{2})\s*[-–]\s*(\d{1,2}[.:]\d{2})", schedule_text)
        if time_match:
            item["time_info"] = f"{time_match.group(1).replace('.', ':')}-{time_match.group(2).replace('.', ':')}"
        elif schedule_text and not any(day.lower() in schedule_text.lower() for day in WEEKDAYS_IT_NAMES):
            item["time_info"] = schedule_text

        # Genera array di date
        dates_array = []
        current_date = date_start

        while current_date <= date_end:
            weekday_num = current_date.weekday()
            weekday_name = WEEKDAYS_IT_NAMES[weekday_num]

            # Se ci sono giorni specificati, filtra
            if allowed_weekdays and weekday_name.lower() not in [d.lower() for d in allowed_weekdays]:
                current_date += timedelta(days=1)
                continue

            # Trova orario per questo giorno
            time_start, time_end = self._get_time_for_day(weekday_name, day_times, schedule_text)

            date_entry = {
                "date": current_date.strftime("%Y-%m-%d"),
                "weekday": weekday_name,
            }

            if time_start:
                date_entry["time_start"] = time_start
            if time_end:
                date_entry["time_end"] = time_end

            dates_array.append(date_entry)
            current_date += timedelta(days=1)

        item["dates"] = dates_array

    def _parse_date(self, date_str):
        """Converte DD/MM/YYYY in oggetto datetime"""
        try:
            return datetime.strptime(date_str, "%d/%m/%Y")
        except ValueError:
            return None

    def _extract_weekdays(self, text):
        """Estrae i giorni della settimana menzionati nel testo"""
        found_days = []
        text_lower = text.lower()
        for day in WEEKDAYS_IT_NAMES:
            if day.lower() in text_lower:
                found_days.append(day)
        return found_days

    def _parse_schedule(self, schedule_text):
        """Parsa lo schedule per estrarre orari specifici per giorno"""
        day_times = {}

        if not schedule_text:
            return day_times

        # Pattern: "Sabato: 10:00-20:00" o "Sabato 10:00-20:00"
        for day in WEEKDAYS_IT_NAMES:
            pattern = rf"{day}[:\s]+(\d{{1,2}}[.:]\d{{2}})\s*[-–]\s*(\d{{1,2}}[.:]\d{{2}})"
            match = re.search(pattern, schedule_text, re.IGNORECASE)
            if match:
                time_start = match.group(1).replace(".", ":")
                time_end = match.group(2).replace(".", ":")
                day_times[day.lower()] = (time_start, time_end)

        # Pattern per gruppi: "dal lunedì al venerdì 9:30-19:30"
        group_pattern = r"dal?\s+(\w+)\s+al?\s+(\w+)\s+(\d{1,2}[.:]\d{2})\s*[-–]\s*(\d{1,2}[.:]\d{2})"
        match = re.search(group_pattern, schedule_text, re.IGNORECASE)
        if match:
            start_day = match.group(1).lower()
            end_day = match.group(2).lower()
            time_start = match.group(3).replace(".", ":")
            time_end = match.group(4).replace(".", ":")

            if start_day in WEEKDAYS_IT and end_day in WEEKDAYS_IT:
                start_idx = WEEKDAYS_IT[start_day]
                end_idx = WEEKDAYS_IT[end_day]
                for i in range(start_idx, end_idx + 1):
                    day_name = WEEKDAYS_IT_NAMES[i].lower()
                    if day_name not in day_times:
                        day_times[day_name] = (time_start, time_end)

        return day_times

    def _get_time_for_day(self, weekday_name, day_times, schedule_text):
        """Ottiene l'orario per un giorno specifico"""
        weekday_lower = weekday_name.lower()

        # Prima cerca orario specifico per giorno
        if weekday_lower in day_times:
            return day_times[weekday_lower]

        # Poi cerca un orario generico nel testo
        time_pattern = r"(\d{1,2}[.:]\d{2})\s*[-–]\s*(\d{1,2}[.:]\d{2})"
        match = re.search(time_pattern, schedule_text)
        if match:
            return (match.group(1).replace(".", ":"), match.group(2).replace(".", ":"))

        # Cerca solo orario singolo
        single_time = re.search(r"(\d{1,2}[.:]\d{2})", schedule_text)
        if single_time:
            return (single_time.group(1).replace(".", ":"), None)

        return (None, None)

    def _extract_price(self, response, info_grid, item):
        """Estrae informazioni sul prezzo"""
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
            item["price"] = self._clean_text(price) if price else None

    def _extract_description(self, response, item):
        """Estrae la descrizione dell'evento"""
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
            item["description"] = desc if desc else None

    def _extract_website(self, response, info_grid, item):
        """Estrae il sito web dell'evento"""
        other_info_section = info_grid.xpath(
            './/span[contains(text(), "Altre informazioni")]/parent::div'
        )
        if not other_info_section:
            other_info_section = response.xpath(
                '//span[contains(text(), "Altre informazioni")]/parent::div[contains(@class, "l-grid__item")]'
            )
        if other_info_section:
            website = other_info_section.css("a::attr(href)").get()
            if website and website.startswith("http"):
                item["website"] = website

    def _clean_text(self, text):
        """Pulisce il testo da spazi extra e caratteri speciali"""
        if text:
            return " ".join(text.split()).strip()
        return None
