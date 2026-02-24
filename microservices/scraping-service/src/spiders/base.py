# -*- coding: utf-8 -*-
"""
Spider base per tutti gli spider di eventi.

Fornisce funzionalità comuni:
- Pulizia testo
- Parsing date
- Generazione hash
- Logging standardizzato
"""

import hashlib
import json
import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List, Dict, Any

import scrapy
from items import EventItem


class BaseEventSpider(scrapy.Spider, ABC):
    """
    Classe base astratta per spider di eventi.

    Ogni spider concreto deve implementare:
    - name: Nome univoco dello spider
    - source_name: Identificativo fonte per il campo 'source'
    - start_requests(): Generazione richieste iniziali
    - parse(): Parsing della risposta

    Parametri comuni accettati:
    - output: Path file output (opzionale)
    """

    # Identificativo fonte (da sovrascrivere nelle sottoclassi)
    source_name: str = "base"

    # Settings di default per tutti gli spider
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
    }

    def __init__(self, output: str = None, *args, **kwargs):
        """
        Inizializza lo spider base.

        Args:
            output: Path opzionale per il file di output
        """
        super().__init__(*args, **kwargs)
        self.output = output

    # =========================================================================
    # METODI DI UTILITÀ PER PULIZIA TESTO
    # =========================================================================

    def clean_text(self, text: Optional[str]) -> Optional[str]:
        """
        Pulisce il testo rimuovendo spazi extra e normalizzando.

        Args:
            text: Testo da pulire

        Returns:
            Testo pulito o None se vuoto
        """
        if not text:
            return None
        # Rimuove spazi multipli e normalizza
        cleaned = " ".join(text.split()).strip()
        return cleaned if cleaned else None

    def clean_html(self, html_text: Optional[str]) -> Optional[str]:
        """
        Rimuove tag HTML dal testo.

        Args:
            html_text: Testo con possibili tag HTML

        Returns:
            Testo senza tag HTML
        """
        if not html_text:
            return None
        # Rimuove tag HTML
        clean = re.sub(r"<[^>]+>", "", html_text)
        return self.clean_text(clean)

    # =========================================================================
    # METODI DI UTILITÀ PER DATE
    # =========================================================================

    def parse_date_dmy(self, date_str: str) -> Optional[str]:
        """
        Converte data DD/MM/YYYY in YYYY-MM-DD.

        Args:
            date_str: Data nel formato DD/MM/YYYY

        Returns:
            Data nel formato YYYY-MM-DD o None
        """
        if not date_str:
            return None
        try:
            dt = datetime.strptime(date_str.strip(), "%d/%m/%Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None

    def parse_date_iso(self, date_str: str) -> Optional[str]:
        """
        Estrae data YYYY-MM-DD da stringa ISO.

        Args:
            date_str: Data in formato ISO (può includere orario)

        Returns:
            Data nel formato YYYY-MM-DD
        """
        if not date_str:
            return None
        match = re.match(r"(\d{4}-\d{2}-\d{2})", date_str)
        return match.group(1) if match else None

    def extract_dates_from_text(self, text: str) -> List[str]:
        """
        Estrae tutte le date DD/MM/YYYY da un testo.

        Args:
            text: Testo contenente date

        Returns:
            Lista di date nel formato YYYY-MM-DD
        """
        if not text:
            return []
        matches = re.findall(r"(\d{2}/\d{2}/\d{4})", text)
        dates = []
        for m in matches:
            parsed = self.parse_date_dmy(m)
            if parsed:
                dates.append(parsed)
        return dates

    # =========================================================================
    # METODI DI UTILITÀ PER HASH
    # =========================================================================

    def generate_uuid(
        self,
        title: str = "",
        date_start: str = "",
        location_name: str = "",
    ) -> str:
        """
        Genera UUID univoco per deduplicazione.

        Args:
            title: Titolo evento
            date_start: Data inizio
            location_name: Nome location

        Returns:
            Hash SHA256 troncato a 16 caratteri
        """
        uuid_string = f"{title}{date_start}{location_name}"
        return hashlib.sha256(uuid_string.encode("utf-8")).hexdigest()[:16]

    def generate_content_hash(
        self,
        description: str = "",
        price: str = "",
        time_start: str = "",
    ) -> str:
        """
        Genera hash del contenuto per rilevare modifiche.

        Args:
            description: Descrizione evento
            price: Prezzo
            time_start: Orario inizio

        Returns:
            Hash SHA256 troncato a 16 caratteri
        """
        content_string = f"{description}{price}{time_start}"
        return hashlib.sha256(content_string.encode("utf-8")).hexdigest()[:16]

    # =========================================================================
    # METODI PER CREAZIONE ITEM
    # =========================================================================

    def create_item(self, **kwargs) -> EventItem:
        """
        Crea un EventItem con valori di default.

        Args:
            **kwargs: Campi dell'item

        Returns:
            EventItem inizializzato
        """
        item = EventItem()
        item["source"] = self.source_name
        item["scraped_at"] = datetime.now().isoformat()

        for key, value in kwargs.items():
            if key in item.fields:
                item[key] = value

        return item

    # =========================================================================
    # METODI DI UTILITÀ JSON-LD
    # =========================================================================

    def extract_jsonld_node(self, response, type_name: str) -> Optional[dict]:
        """
        Cerca e restituisce il primo nodo JSON-LD con @type == type_name.

        Gestisce i tre formati comuni:
        - { "@graph": [{ "@type": "Event", ... }] }
        - { "@type": "Event", ... }
        - [{ "@type": "Event", ... }]

        Args:
            response: Risposta Scrapy con HTML
            type_name: Valore di @type da cercare (es. "Event", "WebPage")

        Returns:
            Dizionario del nodo trovato o None
        """
        for script_text in response.css('script[type="application/ld+json"]::text').getall():
            try:
                data = json.loads(script_text)
            except (json.JSONDecodeError, ValueError):
                continue

            node = self._find_jsonld_node(data, type_name)
            if node:
                return node

        return None

    def _find_jsonld_node(self, data, type_name: str) -> Optional[dict]:
        """Trova il primo nodo con @type == type_name in una struttura JSON-LD."""
        if isinstance(data, dict):
            if "@graph" in data:
                for node in data["@graph"]:
                    if isinstance(node, dict) and node.get("@type") == type_name:
                        return node
            if data.get("@type") == type_name:
                return data
        elif isinstance(data, list):
            for node in data:
                if isinstance(node, dict) and node.get("@type") == type_name:
                    return node
        return None

    # =========================================================================
    # METODI DI UTILITÀ TESTO STRUTTURATO
    # =========================================================================

    def extract_phone_from_text(self, text: str) -> Optional[str]:
        """
        Estrae un numero di telefono dal testo con regex standard italiana.

        Args:
            text: Testo in cui cercare il numero

        Returns:
            Numero di telefono trovato o None
        """
        if not text:
            return None
        match = re.search(r"\b[\d][\d\s.\-/]{5,14}[\d]\b", text)
        return match.group(0).strip() if match else None

    @staticmethod
    def slug_from_url(url: str) -> str:
        """
        Estrae lo slug dall'ultimo segmento dell'URL.

        Args:
            url: URL della pagina evento

        Returns:
            Slug (ultima parte del path, senza slash finale)
        """
        return url.rstrip("/").split("/")[-1]

    # =========================================================================
    # LOGGING
    # =========================================================================

    def log_stats(self, city: str = None):
        """Logga statistiche per città."""
        if city:
            self.crawler.stats.inc_value(f"items_per_city/{city}")
