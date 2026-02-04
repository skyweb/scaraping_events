# -*- coding: utf-8 -*-
"""
Pipeline per l'elaborazione degli eventi.

Pipeline disponibili:
- ValidationPipeline: Valida e pulisce i dati
- HashGeneratorPipeline: Genera UUID e content_hash
- PostgresPipeline: Salva su database PostgreSQL
- ApiPipeline: Invia eventi all'API del backoffice
"""

import hashlib
import json
import logging
import re
from datetime import datetime
from typing import Optional, List, Dict, Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import psycopg2
from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem

logger = logging.getLogger(__name__)


class ValidationPipeline:
    """
    Pipeline per validazione e pulizia dei dati.

    Operazioni:
    - Verifica campi obbligatori (source, url, title)
    - Pulisce testo da spazi extra
    - Normalizza date al formato ISO
    - Converte category in lista se stringa
    """

    REQUIRED_FIELDS = ["source", "url", "title"]

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        # Verifica campi obbligatori
        for field in self.REQUIRED_FIELDS:
            if not adapter.get(field):
                raise DropItem(f"Campo obbligatorio mancante: {field}")

        # Pulisci titolo
        if adapter.get("title"):
            adapter["title"] = self._clean_text(adapter["title"])

        # Pulisci descrizione
        if adapter.get("description"):
            adapter["description"] = self._clean_text(adapter["description"])

        # Normalizza category come lista
        category = adapter.get("category")
        if category:
            if isinstance(category, str):
                adapter["category"] = [c.strip() for c in category.split(",")]
            elif isinstance(category, list):
                adapter["category"] = [c.strip() for c in category if c]

        # Normalizza date
        for field in ["date_start", "date_end"]:
            if adapter.get(field):
                normalized = self._normalize_date(adapter[field])
                if normalized:
                    adapter[field] = normalized

        # Aggiungi timestamp scraping se mancante
        if not adapter.get("scraped_at"):
            adapter["scraped_at"] = datetime.now().isoformat()

        return item

    def _clean_text(self, text: str) -> str:
        """Rimuove spazi extra e caratteri speciali."""
        if not text:
            return text
        # Rimuove tag HTML residui
        text = re.sub(r"<[^>]+>", "", text)
        # Normalizza spazi
        text = " ".join(text.split())
        return text.strip()

    def _normalize_date(self, date_str: str) -> Optional[str]:
        """Converte vari formati data in YYYY-MM-DD."""
        if not date_str:
            return None

        # Già nel formato corretto
        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            return date_str

        # Formato DD/MM/YYYY
        match = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", date_str)
        if match:
            day, month, year = match.groups()
            return f"{year}-{month}-{day}"

        # Formato ISO con timestamp
        match = re.match(r"^(\d{4}-\d{2}-\d{2})", date_str)
        if match:
            return match.group(1)

        return date_str


class HashGeneratorPipeline:
    """
    Pipeline per generazione hash di deduplicazione.

    Genera:
    - uuid: Hash basato su titolo + data_start + location_name
    - content_hash: Hash basato su descrizione + prezzo
    """

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        # Genera UUID se mancante
        if not adapter.get("uuid"):
            uuid_parts = [
                str(adapter.get("title") or ""),
                str(adapter.get("date_start") or ""),
                str(adapter.get("location_name") or ""),
            ]
            uuid_string = "".join(uuid_parts)
            adapter["uuid"] = hashlib.sha256(uuid_string.encode("utf-8")).hexdigest()[:16]

        # Genera content_hash se mancante
        if not adapter.get("content_hash"):
            content_parts = [
                str(adapter.get("description") or ""),
                str(adapter.get("price") or ""),
                str(adapter.get("time_start") or ""),
            ]
            content_string = "".join(content_parts)
            adapter["content_hash"] = hashlib.sha256(content_string.encode("utf-8")).hexdigest()[:16]

        return item


class PostgresPipeline:
    """
    Pipeline per salvataggio su PostgreSQL.

    Configurazione tramite settings:
    - POSTGRES_HOST
    - POSTGRES_PORT
    - POSTGRES_DB
    - POSTGRES_USER
    - POSTGRES_PASSWORD

    La tabella di destinazione è etl.staging_events.
    Usa UPSERT per aggiornare eventi esistenti basandosi su uuid.
    """

    def __init__(self, host, port, database, user, password):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.connection = None
        self.cursor = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            host=crawler.settings.get("POSTGRES_HOST", "localhost"),
            port=crawler.settings.getint("POSTGRES_PORT", 5432),
            database=crawler.settings.get("POSTGRES_DB", "events"),
            user=crawler.settings.get("POSTGRES_USER", "postgres"),
            password=crawler.settings.get("POSTGRES_PASSWORD", "postgres"),
        )

    def open_spider(self, spider):
        """Apre connessione al database."""
        try:
            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
            )
            self.cursor = self.connection.cursor()
            logger.info(f"Connesso a PostgreSQL: {self.host}:{self.port}/{self.database}")
        except psycopg2.Error as e:
            logger.error(f"Errore connessione PostgreSQL: {e}")
            raise

    def close_spider(self, spider):
        """Chiude connessione al database."""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
            logger.info("Connessione PostgreSQL chiusa")

    def process_item(self, item, spider):
        """Salva item su database con UPSERT."""
        adapter = ItemAdapter(item)

        try:
            self.cursor.execute(
                """
                INSERT INTO etl.staging_events (
                    uuid, content_hash, source, url, event_id, slug,
                    title, description, category, image_url,
                    city, city_id, location_name, location_address, location_coords,
                    date_start, date_end, date_display, time_start, time_end,
                    price, website, raw_data, scraped_at
                ) VALUES (
                    %(uuid)s, %(content_hash)s, %(source)s, %(url)s, %(event_id)s, %(slug)s,
                    %(title)s, %(description)s, %(category)s, %(image_url)s,
                    %(city)s, %(city_id)s, %(location_name)s, %(location_address)s, %(location_coords)s,
                    %(date_start)s, %(date_end)s, %(date_display)s, %(time_start)s, %(time_end)s,
                    %(price)s, %(website)s, %(raw_data)s, %(scraped_at)s
                )
                ON CONFLICT (uuid) DO UPDATE SET
                    content_hash = EXCLUDED.content_hash,
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    category = EXCLUDED.category,
                    image_url = EXCLUDED.image_url,
                    location_name = EXCLUDED.location_name,
                    location_address = EXCLUDED.location_address,
                    date_start = EXCLUDED.date_start,
                    date_end = EXCLUDED.date_end,
                    price = EXCLUDED.price,
                    raw_data = EXCLUDED.raw_data,
                    scraped_at = EXCLUDED.scraped_at,
                    updated_at = NOW()
                """,
                {
                    "uuid": adapter.get("uuid"),
                    "content_hash": adapter.get("content_hash"),
                    "source": adapter.get("source"),
                    "url": adapter.get("url"),
                    "event_id": adapter.get("event_id"),
                    "slug": adapter.get("slug"),
                    "title": adapter.get("title"),
                    "description": adapter.get("description"),
                    "category": adapter.get("category"),
                    "image_url": adapter.get("image_url"),
                    "city": adapter.get("city"),
                    "city_id": adapter.get("city_id"),
                    "location_name": adapter.get("location_name"),
                    "location_address": adapter.get("location_address"),
                    "location_coords": adapter.get("location_coords"),
                    "date_start": adapter.get("date_start"),
                    "date_end": adapter.get("date_end"),
                    "date_display": adapter.get("date_display"),
                    "time_start": adapter.get("time_start"),
                    "time_end": adapter.get("time_end"),
                    "price": adapter.get("price"),
                    "website": adapter.get("website"),
                    "raw_data": adapter.get("raw_data"),
                    "scraped_at": adapter.get("scraped_at"),
                },
            )
            self.connection.commit()
        except psycopg2.Error as e:
            logger.error(f"Errore salvataggio evento {adapter.get('uuid')}: {e}")
            self.connection.rollback()

        return item


class ApiPipeline:
    """
    Pipeline per invio eventi all'API del backoffice.

    Configurazione tramite settings:
    - API_BASE_URL: URL base dell'API (es: http://backoffice:8000)
    - API_CLIENT_ID: Client ID OAuth2
    - API_CLIENT_SECRET: Client Secret OAuth2
    - API_BATCH_SIZE: Numero eventi per batch (default: 50)

    Flusso:
    1. Raccoglie eventi in batch
    2. Ottiene token OAuth2
    3. Invia batch all'endpoint /api/external/staging/bulk/
    4. Gestisce retry in caso di errori

    Utilizzo:
        Nel settings.py abilitare:
        ITEM_PIPELINES = {
            ...
            "pipelines.ApiPipeline": 400,
        }
    """

    # Campi da inviare all'API (mappati al StagingEventCreateSerializer)
    API_FIELDS = [
        "uuid", "content_hash", "source", "url", "title", "description",
        "category", "image_url", "city", "location_name", "location_address",
        "price", "website", "date_start", "date_end", "time_start", "time_end",
        "time_info", "schedule", "weekdays", "raw_data", "scraped_at"
    ]

    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        batch_size: int = 50,
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.batch_size = batch_size
        self.timeout = timeout

        self.access_token: Optional[str] = None
        self.items_buffer: List[Dict[str, Any]] = []

        # Configura session con retry
        self.session = self._create_session()

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            base_url=crawler.settings.get("API_BASE_URL", "http://localhost:8000"),
            client_id=crawler.settings.get("API_CLIENT_ID", ""),
            client_secret=crawler.settings.get("API_CLIENT_SECRET", ""),
            batch_size=crawler.settings.getint("API_BATCH_SIZE", 50),
            timeout=crawler.settings.getint("API_TIMEOUT", 30),
        )

    def _create_session(self) -> requests.Session:
        """Crea session HTTP con retry automatici."""
        session = requests.Session()

        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST", "GET"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _get_access_token(self) -> Optional[str]:
        """Ottiene access token OAuth2."""
        if not self.client_id or not self.client_secret:
            logger.error("API_CLIENT_ID e API_CLIENT_SECRET non configurati")
            return None

        token_url = f"{self.base_url}/oauth/token/"

        try:
            response = self.session.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "read write",
                },
                timeout=self.timeout,
            )

            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get("access_token")
                logger.info("Token OAuth2 ottenuto con successo")
                return self.access_token
            else:
                logger.error(f"Errore ottenimento token: {response.status_code} - {response.text}")
                return None

        except requests.RequestException as e:
            logger.error(f"Errore richiesta token: {e}")
            return None

    def _send_batch(self, events: List[Dict[str, Any]]) -> bool:
        """Invia batch di eventi all'API."""
        if not events:
            return True

        if not self.access_token:
            if not self._get_access_token():
                logger.error("Impossibile ottenere token, batch non inviato")
                return False

        bulk_url = f"{self.base_url}/api/external/staging/bulk/"

        try:
            response = self.session.post(
                bulk_url,
                json={"events": events},
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )

            if response.status_code == 201:
                result = response.json()
                logger.info(f"Batch inviato: {result.get('created', 0)} eventi creati")
                return True

            elif response.status_code == 401:
                # Token scaduto, riprova
                logger.warning("Token scaduto, rinnovo...")
                self.access_token = None
                if self._get_access_token():
                    return self._send_batch(events)
                return False

            else:
                logger.error(f"Errore invio batch: {response.status_code} - {response.text}")
                return False

        except requests.RequestException as e:
            logger.error(f"Errore richiesta API: {e}")
            return False

    def _item_to_dict(self, item) -> Dict[str, Any]:
        """Converte item Scrapy in dict per l'API."""
        adapter = ItemAdapter(item)
        data = {}

        for field in self.API_FIELDS:
            value = adapter.get(field)
            if value is not None:
                data[field] = value

        return data

    def open_spider(self, spider):
        """Inizializza pipeline all'avvio dello spider."""
        logger.info(f"ApiPipeline: connessione a {self.base_url}")
        self.items_buffer = []

        # Pre-fetch del token
        if self.client_id and self.client_secret:
            self._get_access_token()

    def close_spider(self, spider):
        """Invia eventi rimanenti alla chiusura dello spider."""
        if self.items_buffer:
            logger.info(f"Invio batch finale: {len(self.items_buffer)} eventi")
            self._send_batch(self.items_buffer)
            self.items_buffer = []

        self.session.close()
        logger.info("ApiPipeline: connessione chiusa")

    def process_item(self, item, spider):
        """Processa item e lo aggiunge al buffer."""
        event_data = self._item_to_dict(item)
        self.items_buffer.append(event_data)

        # Invia batch se raggiunta la dimensione
        if len(self.items_buffer) >= self.batch_size:
            logger.info(f"Invio batch: {len(self.items_buffer)} eventi")
            success = self._send_batch(self.items_buffer)
            if success:
                self.items_buffer = []
            else:
                logger.warning("Batch fallito, mantengo nel buffer per retry")

        return item
