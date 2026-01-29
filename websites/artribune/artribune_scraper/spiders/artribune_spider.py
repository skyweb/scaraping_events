import scrapy
import hashlib
import json
import re
from datetime import datetime
from artribune_scraper.items import EventItem

class ArtribuneSpider(scrapy.Spider):
    name = "artribune"
    allowed_domains = ["artribune.com"]

    # Configurazione
    per_page = 100  # Massimo supportato da WP REST API
    max_pages = None  # None = tutte le pagine

    # Cache dati strutturati dall'endpoint custom (indexed by URL)
    custom_api_data = {}

    def start_requests(self):
        """
        Prima scarica l'endpoint custom per i dati strutturati,
        poi procede con l'endpoint standard per la paginazione completa.
        """
        # 1. Endpoint custom (una sola pagina, dati strutturati)
        yield scrapy.Request(
            "https://www.artribune.com/wp-json/a7e/v1/events",
            callback=self.parse_custom_api,
            priority=10  # Alta priorità
        )

    def parse_custom_api(self, response):
        """
        Parsa l'endpoint custom e memorizza i dati strutturati.
        Poi avvia lo scraping dall'endpoint standard.
        """
        try:
            data = response.json()
            events = data.get('events', []) if isinstance(data, dict) else data

            self.logger.info(f"Endpoint custom: {len(events)} eventi con dati strutturati")

            # Memorizza dati per URL
            for event in events:
                url = event.get('url')
                if url:
                    self.custom_api_data[url] = {
                        'place': event.get('place', {}),
                        'dates_html': event.get('dates'),
                        'image_html': event.get('image'),
                        'excerpt': event.get('excerpt'),
                    }

            self.logger.info(f"Memorizzati {len(self.custom_api_data)} eventi dall'API custom")

        except Exception as e:
            self.logger.warning(f"Errore parsing API custom: {e}")

        # 2. Avvia scraping dall'endpoint standard (paginazione completa)
        yield scrapy.Request(
            f"https://www.artribune.com/wp-json/wp/v2/event?per_page={self.per_page}&page=1",
            callback=self.parse
        )

    def parse(self, response):
        """
        Estrae gli eventi dalla risposta JSON delle API WP REST.
        Gestisce la paginazione tramite header X-WP-TotalPages.
        """
        try:
            events_list = response.json()

            # Estrai info paginazione dagli header
            total_events = int(response.headers.get('X-WP-Total', b'0').decode())
            total_pages = int(response.headers.get('X-WP-TotalPages', b'0').decode())

            # Calcola pagina corrente dall'URL
            page_match = re.search(r'[?&]page=(\d+)', response.url)
            current_page = int(page_match.group(1)) if page_match else 1

            self.logger.info(f"Pagina {current_page} di {total_pages}. Totale eventi: {total_events}")

            if not events_list:
                self.logger.info("Nessun evento trovato. Fine paginazione.")
                return

            for event_data in events_list:
                item = EventItem()

                # URL della pagina evento
                item['url'] = event_data.get('link')

                # Estrai titolo (è un oggetto con 'rendered')
                title_obj = event_data.get('title', {})
                item['title'] = title_obj.get('rendered') if isinstance(title_obj, dict) else title_obj

                # Salva dati originali dall'API WP REST
                item['raw_data'] = {
                    'id': event_data.get('id'),
                    'slug': event_data.get('slug'),
                    'date_published': event_data.get('date'),
                }

                # Arricchisci con dati dall'API custom se disponibili
                custom_data = self.custom_api_data.get(item['url'], {})
                if custom_data:
                    item['raw_data']['custom_api'] = custom_data

                    # Estrai dati strutturati da place
                    place = custom_data.get('place', {})
                    if isinstance(place, dict):
                        item['location_name'] = place.get('title')
                        place_map = place.get('map', {})
                        if isinstance(place_map, dict):
                            item['location_address'] = place_map.get('address')
                        place_city = place.get('city', {})
                        if isinstance(place_city, dict):
                            city_title = place_city.get('title', '')
                            item['city'] = re.sub(r'\s*\([A-Z]{2}\)$', '', city_title).strip()

                    # Estrai date dal campo dates HTML
                    dates_html = custom_data.get('dates_html', '')
                    if dates_html and '<time' in dates_html:
                        dt_matches = re.findall(r'datetime=["\'](\d{4}-\d{2}-\d{2})["\']', dates_html)
                        if len(dt_matches) >= 1:
                            item['date_start'] = dt_matches[0]
                        if len(dt_matches) >= 2:
                            item['date_end'] = dt_matches[1]
                        elif len(dt_matches) == 1:
                            item['date_end'] = dt_matches[0]

                    # Estrai immagini
                    image_html = custom_data.get('image_html', '')
                    item['image_urls'] = []
                    if image_html and '<img' in image_html:
                        urls = re.findall(r'src=["\'](.*?)["\']', image_html)
                        item['image_urls'].extend(urls)
                        if urls:
                            item['image_url'] = urls[0]
                else:
                    item['image_urls'] = []

                # Visita la pagina di dettaglio per estrarre tutti i dati
                if item['url']:
                    yield response.follow(
                        item['url'],
                        callback=self.parse_event_detail,
                        meta={'item': item}
                    )
                else:
                    self._generate_hashes(item)
                    item['scraped_at'] = datetime.now().isoformat()
                    yield item

            # Paginazione: vai alla pagina successiva (nessun limite)
            max_pages = self.max_pages or total_pages
            if current_page < max_pages:
                next_page = current_page + 1
                next_url = f"https://www.artribune.com/wp-json/wp/v2/event?per_page={self.per_page}&page={next_page}"
                self.logger.info(f"Paginazione: richiedo pagina {next_page}")
                yield scrapy.Request(next_url, callback=self.parse)

        except Exception as e:
            self.logger.error(f"Errore parsing API pagina {response.url}: {e}")

    def parse_event_detail(self, response):
        """
        Estrae dettagli aggiuntivi dalla pagina singola dell'evento.
        """
        item = response.meta['item']
        self.logger.info(f"Scraping dettaglio: {item.get('title')}")
        
        # 1. Tenta di estrarre ulteriori dati da JSON-LD di dettaglio
        json_ld_detail = response.xpath('//script[@type="application/ld+json" and contains(text(), "Event")]/text()').get()
        if json_ld_detail:
            try:
                detail_data = json.loads(json_ld_detail)
                event_obj = None
                if isinstance(detail_data, dict):
                    if "@graph" in detail_data:
                        events = [x for x in detail_data["@graph"] if x.get("@type") == "Event"]
                        if events: event_obj = events[0]
                    elif detail_data.get("@type") == "Event":
                        event_obj = detail_data
                elif isinstance(detail_data, list):
                    events = [x for x in detail_data if x.get("@type") == "Event"]
                    if events: event_obj = events[0]

                if event_obj:
                    # Immagini dal JSON-LD di dettaglio
                    ld_images = event_obj.get('image')
                    if ld_images:
                        if isinstance(ld_images, list):
                            item['image_urls'].extend(ld_images)
                        else:
                            item['image_urls'].append(ld_images)
                    
                    # Prezzo
                    offers = event_obj.get('offers', {})
                    if isinstance(offers, dict):
                        price = offers.get('price')
                        if price: item['price'] = str(price)
                    elif isinstance(offers, list) and offers:
                        price = offers[0].get('price')
                        if price: item['price'] = str(price)
                    
                    # Arricchisci date se mancano
                    if not item.get('date_start'):
                        item['date_start'] = event_obj.get('startDate')
                    if not item.get('date_end'):
                        item['date_end'] = event_obj.get('endDate')

            except Exception as e:
                self.logger.warning(f"Errore parsing JSON-LD dettaglio su {response.url}: {e}")

        # 2. Estrazione da HTML (Raffinata sui dati reali di Artribune)

        # Estrazione strutturata "Informazioni Evento" box
        # Struttura tipica: <dl><dt><svg/><span class="u-sr">Label</span></dt><dd>Value</dd></dl>
        info_dls = response.xpath('//div[contains(@class, "c-widget_content")]/dl')
        event_info = {}

        if info_dls:
            self.logger.info(f"Trovati {len(info_dls)} elementi DL nel widget info.")

        for dl in info_dls:
            # Cerca la chiave in diversi posti:
            # 1. Span con classe screen-reader (u-sr, sr-only, visually-hidden)
            key = dl.xpath('.//dt//span[contains(@class, "sr") or contains(@class, "hidden")]//text()').get()

            # 2. Testo diretto nel dt (escludendo svg)
            if not key:
                dt_texts = dl.xpath('.//dt/text() | .//dt/span/text()').getall()
                key = " ".join([t.strip() for t in dt_texts if t.strip()])

            # 3. Attributo title o aria-label sul dt
            if not key:
                key = dl.xpath('.//dt/@title | .//dt/@aria-label').get()

            # 4. Primo dd come chiave se dt è solo icona (struttura alternativa)
            dds = dl.xpath('.//dd')
            if not key and len(dds) >= 2:
                # Primo dd potrebbe essere la label
                first_dd_text = dds[0].xpath('.//text()').getall()
                key = " ".join([t.strip() for t in first_dd_text if t.strip()])
                dds = dds[1:]  # I restanti dd sono i valori

            if key:
                key = key.strip()
                values = []
                for dd in dds:
                    text_parts = dd.xpath('.//text()').getall()
                    text = " ".join([t.strip() for t in text_parts if t.strip()])
                    text = text.replace('(Clicca qui per la mappa)', '').strip()
                    if text:
                        values.append(text)

                if values:
                    event_info[key] = "\n".join(values)
        
        # Aggiungiamo anche ai raw_data per completezza se richiesto
        if 'raw_data' in item and isinstance(item['raw_data'], dict):
            item['raw_data']['event_info'] = event_info

        # Mappatura specifica da event_info se mancano dati
        if not item.get('location_name'):
            item['location_name'] = event_info.get('Luogo')
        
        # Generi
        if not item.get('category') and 'Generi' in event_info:
            gens = event_info['Generi']
            if isinstance(gens, str):
                item['category'] = [g.strip() for g in gens.split(',')]
            else:
                # Se è lista, uniscila e splitta
                full_gens = ", ".join(gens)
                item['category'] = [g.strip() for g in full_gens.split(',')]

        # Città (dal breadcrumb o dal box info)
        if not item.get('city'):
            # Prova dal breadcrumb: Home > Eventi > Roma > Titolo
            city_breadcrumb = response.xpath('//nav[contains(@class, "c-breadcrumb")]/a[contains(@href, "/mostre/")]/text()').get()
            if city_breadcrumb:
                item['city'] = city_breadcrumb.strip()

        # Date (se mancano nel JSON e in event_info)
        if not item.get('date_start'):
            d_start = response.xpath('//time[1]/@datetime').get()
            if d_start: item['date_start'] = d_start
        if not item.get('date_end'):
            d_end = response.xpath('//time[2]/@datetime').get()
            if d_end: item['date_end'] = d_end

        # Location Name fallback
        if not item.get('location_name'):
            loc_name = response.xpath('//header//ul[contains(@class, "-meta")]//a[contains(@href, "/museo-galleria-arte/")]/text()').get()
            item['location_name'] = loc_name.strip() if loc_name else None

        # Indirizzo da event_info o fallback
        if not item.get('location_address') and 'Luogo' in event_info:
            # Di solito il secondo valore di Luogo è l'indirizzo
            vals = event_info['Luogo']
            if isinstance(vals, list) and len(vals) > 1:
                item['location_address'] = vals[1]
        
        if not item.get('location_address'):
             full_address = response.xpath('//dl[dt[contains(text(), "Luogo")]]/dd[2]/text()').get()
             if full_address:
                item['location_address'] = full_address.replace('(Clicca qui per la mappa)', '').strip()

        # Descrizione completa
        content_div = response.css('.c-content.-post')
        if content_div:
            parts = content_div.xpath('.//p//text() | .//h2//text()').getall()
            if parts:
                full_desc = " ".join([p.strip() for p in parts if p.strip()])
                if len(full_desc) > len(item.get('description', '') or ''):
                    item['description'] = full_desc

        # Orari / Info aggiuntive
        if not item.get('schedule'):
            time_match = response.xpath('//p[contains(text(), "Orari")]/text()').get()
            if time_match:
                item['schedule'] = time_match.strip()

        if not item.get('price'):
            price_text = response.xpath('//text()[contains(., "Biglietti") or contains(., "Costo")]/following::text()[1]').get()
            if price_text:
                item['price'] = price_text.strip()

        # 3. Altre immagini dal dettaglio (Gallery, Featured Image HTML)
        featured_img = response.css('.c-featured img::attr(src)').get()
        if featured_img:
            item['image_urls'].append(featured_img)
            
        gallery_imgs = response.css('.swiper-slide img::attr(src), .gallery-item img::attr(src)').getall()
        if gallery_imgs:
            item['image_urls'].extend(gallery_imgs)

        # Pulizia finale image_urls: rimuovi duplicati, None e spazi
        clean_urls = []
        seen = set()
        for u in item.get('image_urls', []):
            if u and isinstance(u, str):
                u = u.strip()
                if u not in seen:
                    clean_urls.append(u)
                    seen.add(u)
        
        item['image_urls'] = clean_urls
        # Aggiorna immagine principale se non impostata
        if not item.get('image_url') and clean_urls:
            item['image_url'] = clean_urls[0]

        # Generazione UUID e Hash Finali
        self._generate_hashes(item)
        item['scraped_at'] = datetime.now().isoformat()

        yield item

    def _generate_hashes(self, item):
        """Genera UUID e content_hash per deduplicazione"""
        s_title = item.get('title') or ""
        s_id = item.get('id') or ""

        uuid_string = f"{s_title}{s_id}"
        item["uuid"] = hashlib.sha256(uuid_string.encode('utf-8')).hexdigest()[:16]

        c_desc = item.get('description') or ""
        c_price = item.get('price') or ""

        content_string = f"{c_desc}{c_price}"
        item["content_hash"] = hashlib.sha256(content_string.encode('utf-8')).hexdigest()[:16]
