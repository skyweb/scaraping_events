import json
import os
import re
from datetime import datetime

import scrapy

from comuni_istat.items import ComuneItem, ProvinciaItem, RegioneItem


class ComuniSpider(scrapy.Spider):
    """Spider per scaricare dati su regioni, province e comuni italiani
    dal sito comuni-italiani.it.

    Struttura HTML del sito:
    - Label/valore in righe <tr> con td.ivoce (label) e secondo td (valore)
    - Popolazione/Densità/Superficie in blocco speciale dopo td.itit
    - Sezioni extra in td.itit seguite da righe con dati (icona point.gif + testo)
    - Link province: ../NNN/index.html
    - Link comuni: NNN/index.html

    In caso di errore su una pagina, lo spider continua con le altre
    e scrive gli errori in data/output/errori.log
    """

    name = "comuni_spider"
    allowed_domains = ["www.comuni-italiani.it"]
    start_urls = ["https://www.comuni-italiani.it/regioni.html"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._errori = []

    # --- Gestione errori ---

    def _log_errore(self, livello, url, messaggio):
        """Registra un errore nel log interno (scritto su file in close)."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "livello": livello,
            "url": url,
            "messaggio": messaggio,
        }
        self._errori.append(entry)
        self.logger.warning(f"[{livello}] {url} - {messaggio}")

    def _errback_request(self, failure):
        """Callback per errori HTTP/rete sulle request."""
        url = failure.request.url
        self._log_errore("HTTP", url, str(failure.value))

    def closed(self, reason):
        """Scrive il file errori.log alla chiusura dello spider."""
        if not self._errori:
            return

        output_dir = os.environ.get(
            "OUTPUT_DIR",
            os.path.join(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                ),
                "data",
                "output",
            ),
        )
        os.makedirs(output_dir, exist_ok=True)
        log_path = os.path.join(output_dir, "errori.log")
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(self._errori, f, ensure_ascii=False, indent=2)
        self.logger.info(
            f"Scritti {len(self._errori)} errori in {log_path}"
        )

    # --- Helpers per il parsing dei valori ---

    def _parse_numero(self, testo):
        """Converte stringa con separatore italiano (es. '1.322.247') in int."""
        if not testo:
            return None
        pulito = re.sub(r"[.\s]", "", testo.strip())
        try:
            return int(pulito)
        except (ValueError, TypeError):
            return None

    def _parse_decimale(self, testo):
        """Converte stringa decimale italiana (es. '122,5') in float."""
        if not testo:
            return None
        pulito = testo.strip().replace(".", "").replace(",", ".")
        pulito = re.sub(r"[^\d.]", "", pulito)
        try:
            return float(pulito)
        except (ValueError, TypeError):
            return None

    def _get_field(self, response, label):
        """Estrae il valore testuale dal secondo td nella riga con td.ivoce matching."""
        row = response.xpath(
            f'//td[@class="ivoce" and contains(text(), "{label}")]/parent::tr'
        )
        if row:
            value_td = row.xpath("td[2]")
            if value_td:
                return value_td.xpath("string(.)").get("").strip()
        return ""

    def _get_field_link(self, response, label):
        """Come _get_field ma prova prima il testo del link <a>."""
        row = response.xpath(
            f'//td[@class="ivoce" and contains(text(), "{label}")]/parent::tr'
        )
        if row:
            value_td = row.xpath("td[2]")
            if value_td:
                link_text = value_td.css("a::text").get()
                if link_text:
                    return link_text.strip()
                return value_td.xpath("string(.)").get("").strip()
        return ""

    def _get_section_items(self, response, keyword):
        """Estrae la lista di elementi da una sezione td.itit."""
        itit = response.xpath(
            f'//td[@class="itit" and contains(text(), "{keyword}")]'
        )
        if not itit:
            return []

        parent_tr = itit.xpath("ancestor::tr[1]")
        if not parent_tr:
            return []

        items = []
        next_trs = parent_tr.xpath("following-sibling::tr")
        for tr in next_trs:
            if tr.xpath("td[@class='itit'] | td[@class='ivoce']"):
                break
            if tr.xpath(".//table"):
                break
            text = tr.xpath("string(.)").get("").strip()
            if text:
                items.append(text)

        return items

    def _get_section_text(self, response, keyword):
        """Estrae il testo libero da una sezione td.itit (es. Etimologia)."""
        items = self._get_section_items(response, keyword)
        return " ".join(items).strip() if items else None

    def _get_section_list(self, response, keyword):
        """Estrae una lista di elementi da una sezione td.itit."""
        items = self._get_section_items(response, keyword)
        if not items:
            return []

        if len(items) == 1 and "," in items[0]:
            return [x.strip() for x in items[0].split(",") if x.strip()]

        return items

    def _get_stazioni(self, response):
        """Estrae le stazioni ferroviarie dalla tabella annidata."""
        itit = response.xpath(
            '//td[@class="itit" and contains(text(), "Stazioni Ferroviarie")]'
        )
        if not itit:
            return []

        parent_tr = itit.xpath("ancestor::tr[1]")
        table = parent_tr.xpath(
            "following-sibling::tr[1]//table//tr[td and not(th)]"
        )

        stazioni = []
        for row in table:
            cells = row.xpath("td")
            if len(cells) >= 2:
                nome = cells[0].xpath("string(.)").get("").strip()
                indirizzo = cells[1].xpath("string(.)").get("").strip()
                if nome and nome != "Stazione":
                    stazione = {"nome": nome, "indirizzo": indirizzo}
                    if len(cells) >= 3:
                        stazione["gestore"] = (
                            cells[2].xpath("string(.)").get("").strip()
                        )
                    if len(cells) >= 4:
                        stazione["categoria"] = (
                            cells[3].xpath("string(.)").get("").strip()
                        )
                    stazioni.append(stazione)
        return stazioni

    def _parse_popolazione_block(self, response):
        """Estrae popolazione, densità e superficie dal blocco speciale."""
        pop_td = response.xpath(
            '//td[@class="itit" and contains(text(), "Popolazione Residente")]'
            "/ancestor::tr/following-sibling::tr[1]/td"
        )
        if not pop_td:
            return None, None, None, None, None

        raw_text = pop_td.xpath("string(.)").get("")

        pop_bold = pop_td.css("b::text").get("")
        totale = self._parse_numero(pop_bold)

        match_mf = re.search(r"M\s*([\d.]+).*?F\s*([\d.]+)", raw_text)
        maschi = self._parse_numero(match_mf.group(1)) if match_mf else None
        femmine = self._parse_numero(match_mf.group(2)) if match_mf else None

        match_dens = re.search(r"Densit[àa]?\s+per\s+Kmq:\s*([\d.,]+)", raw_text)
        densita = self._parse_decimale(match_dens.group(1)) if match_dens else None

        match_sup = re.search(r"Superficie:\s*([\d.,]+)", raw_text)
        superficie = self._parse_decimale(match_sup.group(1)) if match_sup else None

        return totale, maschi, femmine, densita, superficie

    # --- Parsing pagina elenco regioni ---

    def parse(self, response):
        """Parsing della pagina /regioni.html - estrae link a tutte le regioni."""
        rows = response.xpath("//table//tr[td]")
        for row in rows:
            link = row.xpath("td[1]//a/@href").get()
            if link and re.match(r"\d{2}/index\.html", link):
                yield response.follow(
                    link,
                    callback=self.parse_regione,
                    errback=self._errback_request,
                )

    # --- Parsing pagina singola regione ---

    def parse_regione(self, response):
        """Parsing della pagina di una regione - estrae dati e segue link province."""
        try:
            yield from self._parse_regione_inner(response)
        except Exception as e:
            self._log_errore("PARSE_REGIONE", response.url, str(e))

    def _parse_regione_inner(self, response):
        h1 = response.css("h1::text").get("")
        nome = re.sub(r"^Regione\s+", "", h1).strip()

        if not nome:
            self._log_errore("PARSE_REGIONE", response.url, "Nome regione non trovato")
            return

        popolazione, maschi, femmine, densita, superficie = (
            self._parse_popolazione_block(response)
        )

        num_comuni = self._get_field(response, "Numero Comuni")
        num_province = self._get_field(response, "Numero Province")
        capoluogo = self._get_field_link(response, "Capoluogo")
        codice_istat = self._get_field(response, "Codice Istat")
        iso_3166_2 = self._get_field(response, "ISO 3166-2")
        nuts = self._get_field(response, "NUTS")

        yield RegioneItem(
            nome=nome,
            codice_istat=codice_istat or None,
            popolazione=popolazione,
            popolazione_maschi=maschi,
            popolazione_femmine=femmine,
            superficie_kmq=superficie,
            densita=densita,
            num_province=self._parse_numero(num_province),
            num_comuni=self._parse_numero(num_comuni),
            capoluogo=capoluogo or None,
            iso_3166_2=iso_3166_2 or None,
            nuts=nuts or None,
        )

        for link in response.css("a::attr(href)").getall():
            if re.match(r"\.\./\d{3}/index\.html$", link):
                yield response.follow(
                    link,
                    callback=self.parse_provincia,
                    errback=self._errback_request,
                    cb_kwargs={"regione_nome": nome},
                )

    # --- Parsing pagina singola provincia ---

    def parse_provincia(self, response, regione_nome):
        """Parsing della pagina di una provincia - estrae dati e segue link comuni."""
        try:
            yield from self._parse_provincia_inner(response, regione_nome)
        except Exception as e:
            self._log_errore("PARSE_PROVINCIA", response.url, str(e))

    def _parse_provincia_inner(self, response, regione_nome):
        h1 = response.css("h1::text").get("")
        nome = re.sub(
            r"^Provincia\s+(di|del|dell[a']|dello|dei|degli|delle)\s+",
            "", h1, flags=re.IGNORECASE,
        ).strip()

        if not nome:
            self._log_errore(
                "PARSE_PROVINCIA", response.url, "Nome provincia non trovato"
            )
            return

        popolazione, maschi, femmine, densita, superficie = (
            self._parse_popolazione_block(response)
        )

        zona = self._get_field(response, "Zona")
        num_comuni = self._get_field(response, "Numero Comuni")
        capoluogo = self._get_field_link(response, "Capoluogo")
        sigla = self._get_field(response, "Sigla")
        codice_istat = self._get_field(response, "Codice Istat")
        iso_3166_2 = self._get_field(response, "ISO 3166-2")
        nuts = self._get_field(response, "NUTS")

        yield ProvinciaItem(
            nome=nome,
            regione=regione_nome,
            zona=zona or None,
            sigla=sigla or None,
            codice_istat=codice_istat or None,
            popolazione=popolazione,
            popolazione_maschi=maschi,
            popolazione_femmine=femmine,
            superficie_kmq=superficie,
            densita=densita,
            num_comuni=self._parse_numero(num_comuni),
            capoluogo=capoluogo or None,
            iso_3166_2=iso_3166_2 or None,
            nuts=nuts or None,
        )

        for link in response.css("a::attr(href)").getall():
            if re.match(r"\d{3}/index\.html$", link):
                yield response.follow(
                    link,
                    callback=self.parse_comune,
                    errback=self._errback_request,
                    cb_kwargs={
                        "regione_nome": regione_nome,
                        "provincia_nome": nome,
                    },
                )

    # --- Parsing pagina singolo comune ---

    def parse_comune(self, response, regione_nome, provincia_nome):
        """Parsing della pagina di un comune - estrae tutti i dati."""
        try:
            yield from self._parse_comune_inner(response, regione_nome, provincia_nome)
        except Exception as e:
            self._log_errore("PARSE_COMUNE", response.url, str(e))

    def _parse_comune_inner(self, response, regione_nome, provincia_nome):
        heading = response.css("h1::text").get("")
        nome = re.sub(r"^Comune\s+di\s+", "", heading, flags=re.IGNORECASE).strip()

        if not nome:
            self._log_errore(
                "PARSE_COMUNE", response.url, "Nome comune non trovato"
            )
            return

        popolazione, _, _, densita, superficie = (
            self._parse_popolazione_block(response)
        )

        zona = self._get_field(response, "Zona")
        cap = self._get_field_link(response, "CAP")
        prefisso = self._get_field(response, "Telefonico")
        codice_istat = self._get_field(response, "Codice Istat")
        codice_catastale = self._get_field_link(response, "Codice Catastale")
        patrono = self._get_field(response, "Santo Patrono")
        festa = self._get_field_link(response, "Festa Patronale")
        demonimo = self._get_field(response, "Denominazione Abitanti")

        if prefisso:
            prefisso = re.sub(r"(?i)prefisso\s*", "", prefisso).strip()

        # --- Sezioni extra ---
        etimologia = self._get_section_text(response, "Etimologia")
        il_comune_e = self._get_section_list(response, "è:")
        fa_parte_di = self._get_section_list(response, "fa parte di")
        localita_frazioni = self._get_section_list(response, "Frazioni di")
        comuni_confinanti = self._get_section_list(response, "Comuni Confinanti")
        musei = self._get_section_list(response, "Musei nel Comune")
        ville_palazzi = self._get_section_list(response, "Ville e Palazzi")
        chiese = self._get_section_list(response, "Chiese e altri edifici")
        castelli = self._get_section_list(response, "Castelli e Fortificazioni")
        fontane = self._get_section_list(response, "Fontane")
        giardini = self._get_section_list(response, "Giardini e Orto")
        luoghi_interesse = self._get_section_list(response, "Luoghi di Interesse")
        teatri = self._get_section_list(response, "Teatri")
        stadi = self._get_section_list(response, "Stadi di Calcio")
        eventi = self._get_section_list(response, "Eventi, Feste e Sagre")
        gemellaggi = self._get_section_list(response, "gemellato con")
        stazioni = self._get_stazioni(response)
        cittadini_illustri = self._get_section_list(response, "Cittadini Illustri")

        self.logger.info(f"    [COMUNE] {regione_nome} - {nome}")

        yield ComuneItem(
            nome=nome,
            provincia=provincia_nome,
            regione=regione_nome,
            zona=zona or None,
            codice_istat=codice_istat or None,
            codice_catastale=codice_catastale or None,
            popolazione=popolazione,
            superficie_kmq=superficie,
            densita=densita,
            cap=cap or None,
            prefisso_telefonico=prefisso or None,
            patrono=patrono or None,
            festa_patronale=festa or None,
            demonimo=demonimo or None,
            # Sezioni extra
            etimologia=etimologia,
            il_comune_e=il_comune_e or None,
            fa_parte_di=fa_parte_di or None,
            localita_frazioni=localita_frazioni or None,
            comuni_confinanti=comuni_confinanti or None,
            musei=musei or None,
            ville_palazzi=ville_palazzi or None,
            chiese=chiese or None,
            castelli_fortificazioni=castelli or None,
            fontane=fontane or None,
            giardini_orti_botanici=giardini or None,
            luoghi_interesse=luoghi_interesse or None,
            teatri=teatri or None,
            stadi=stadi or None,
            eventi_feste_sagre=eventi or None,
            gemellaggi=gemellaggi or None,
            stazioni_ferroviarie=stazioni or None,
            cittadini_illustri=cittadini_illustri or None,
        )
