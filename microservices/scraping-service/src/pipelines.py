# -*- coding: utf-8 -*-
"""
Pipeline per l'elaborazione degli eventi.

Pipeline disponibili:
- ValidationPipeline: Valida e pulisce i dati
- BatchExportPipeline: Esporta batch JSON (senza API, per test/debug)
- ApiPipeline: Invia eventi all'API del backoffice
"""

import html
import json
import logging
import os
import re
from datetime import datetime
from typing import Optional, List, Dict, Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from itemadapter import ItemAdapter
from scrapy.exceptions import CloseSpider, DropItem

from otel_setup import tracer, airflow_context

logger = logging.getLogger(__name__)


# =============================================================================
# Storage Backend (filesystem / MinIO S3)
# =============================================================================
# Configurabile via setting STORAGE_BACKEND=local|minio
# Da CLI:  scrapy crawl spider -s STORAGE_BACKEND=minio
# Da API:  curl .../schedule.json -d setting=STORAGE_BACKEND=minio
# =============================================================================

class StorageBackend:
    """Astrazione per il salvataggio file su filesystem locale o MinIO (S3)."""

    def __init__(self, backend: str = "local", output_dir: str = "/data/output"):
        self.backend = backend
        self.output_dir = output_dir
        self._s3_client = None
        self._bucket = os.environ.get("MINIO_BUCKET", "scraping-output")

    def init(self):
        """Inizializza il backend."""
        if self.backend == "minio":
            self._init_minio()
        else:
            os.makedirs(self.output_dir, exist_ok=True)

    def _init_minio(self):
        """Crea il client S3 per MinIO e assicura che il bucket esista."""
        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            raise CloseSpider(
                "STORAGE_BACKEND=minio richiede boto3: pip install boto3"
            )

        self._s3_client = boto3.client(
            "s3",
            endpoint_url=os.environ.get("MINIO_ENDPOINT", "http://minio:9000"),
            aws_access_key_id=os.environ.get("MINIO_ACCESS_KEY", "minioadmin"),
            aws_secret_access_key=os.environ.get("MINIO_SECRET_KEY", "minioadmin_secret_2026"),
            region_name="us-east-1",
            config=Config(signature_version="s3v4"),
        )

        # Crea il bucket se non esiste
        try:
            self._s3_client.head_bucket(Bucket=self._bucket)
        except Exception:
            try:
                self._s3_client.create_bucket(Bucket=self._bucket)
                logger.info(f"Bucket MinIO creato: {self._bucket}")
            except Exception as e:
                raise CloseSpider(f"Impossibile creare bucket MinIO '{self._bucket}': {e}")

        logger.info(f"StorageBackend: MinIO ({self._bucket})")

    def build_path(self, filename: str, prefix: str = "") -> str:
        """Restituisce il path/key dove verrà salvato il file (senza salvarlo)."""
        if self.backend == "minio":
            key = f"{prefix}/{filename}" if prefix else filename
            return f"s3://{self._bucket}/{key}"
        else:
            return os.path.join(self.output_dir, filename)

    def save_json(self, filename: str, data: dict, prefix: str = "") -> str:
        """
        Salva un dict come file JSON.

        Restituisce il percorso/key del file salvato.
        """
        content = json.dumps(data, ensure_ascii=False, indent=2, default=str)

        if self.backend == "minio":
            key = f"{prefix}/{filename}" if prefix else filename
            try:
                self._s3_client.put_object(
                    Bucket=self._bucket,
                    Key=key,
                    Body=content.encode("utf-8"),
                    ContentType="application/json",
                )
                logger.info(f"Salvato su MinIO: s3://{self._bucket}/{key}")
                return f"s3://{self._bucket}/{key}"
            except Exception as e:
                logger.warning(f"Errore upload MinIO: {e}")
                # Fallback su filesystem
                return self._save_local(filename, content, prefix)
        else:
            return self._save_local(filename, content, prefix)

    def _save_local(self, filename: str, content: str, prefix: str = "") -> str:
        """Salva su filesystem locale, creando sottocartelle se prefix è specificato."""
        target_dir = os.path.join(self.output_dir, prefix) if prefix else self.output_dir
        os.makedirs(target_dir, exist_ok=True)
        filepath = os.path.join(target_dir, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as e:
            logger.warning(f"Impossibile salvare file: {e}")
        return filepath


class ValidationPipeline:
    """
    Pipeline per validazione e pulizia dei dati.

    Operazioni:
    - Verifica campi obbligatori (source, url, title)
    - Pulisce testo da spazi extra
    - Normalizza date al formato ISO
    - Converte category in lista se stringa
    """

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        data = adapter.get("data") or {}
        meta = adapter.get("meta") or {}

        # Verifica campi obbligatori
        if not adapter.get("title"):
            raise DropItem("Campo obbligatorio mancante: title")
        if not meta.get("source"):
            raise DropItem("Campo obbligatorio mancante: meta.source")
        if not meta.get("url"):
            raise DropItem("Campo obbligatorio mancante: meta.url")

        # Pulisci titolo
        adapter["title"] = self._clean_text(adapter["title"])

        # Normalizza category come lista
        category = data.get("category")
        if category:
            if isinstance(category, str):
                data["category"] = [c.strip() for c in category.split(",")]
            elif isinstance(category, list):
                data["category"] = [c.strip() for c in category if c]

        # Normalizza date (dentro data.dates)
        dates = data.get("dates") or {}
        for field in ["date_start", "date_end"]:
            if dates.get(field):
                normalized = self._normalize_date(dates[field])
                if normalized:
                    dates[field] = normalized
        data["dates"] = dates

        # Aggiorna data nell'item
        adapter["data"] = data

        return item

    def _clean_text(self, text: str) -> str:
        """Rimuove spazi extra e caratteri speciali."""
        if not text:
            return text
        # Decodifica HTML entities (&#8217; → ', &amp; → &, ecc.)
        text = html.unescape(text)
        # Rimuove tag HTML residui
        text = re.sub(r"<[^>]+>", "", text)
        # Normalizza spazi
        text = " ".join(text.split())
        return text.strip()

    def _normalize_date(self, date_str: str) -> Optional[str]:
        """Converte vari formati data in YYYY-MM-DD o YYYY-MM-DD HH:MM."""
        if not date_str:
            return None

        # YYYY-MM-DD HH:MM (già nel formato corretto con orario)
        if re.match(r"^\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}$", date_str):
            return date_str

        # YYYY-MM-DD (già nel formato corretto senza orario)
        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            return date_str

        # Formato DD/MM/YYYY
        match = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", date_str)
        if match:
            day, month, year = match.groups()
            return f"{year}-{month}-{day}"

        # Formato ISO con timestamp (es: 2026-02-06T20:30:00)
        match = re.match(r"^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})", date_str)
        if match:
            return f"{match.group(1)} {match.group(2)}"

        # Formato ISO solo data
        match = re.match(r"^(\d{4}-\d{2}-\d{2})", date_str)
        if match:
            return match.group(1)

        return date_str


class BatchExportPipeline:
    """Pipeline base per esportazione batch JSON.

    Gestisce buffer separati per ogni category (meta.category).
    Ogni category accumula item indipendentemente e flusha al raggiungimento di batch_size.
    Nome file: {spider}_{category}_{timestamp}_batch_{N}.json
    """

    def __init__(self, batch_size: int = 50, storage_backend: str = "local"):
        self.batch_size = batch_size
        self.storage = StorageBackend(backend=storage_backend)
        self.spider_name = ""
        # Buffer separato per ogni category
        self._buffers: Dict[str, List[Dict[str, Any]]] = {}
        self._batch_counts: Dict[str, int] = {}
        self._total_batches = 0

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            batch_size=crawler.settings.getint("API_BATCH_SIZE", 50),
            storage_backend=crawler.settings.get("STORAGE_BACKEND", "local"),
        )

    def open_spider(self, spider):
        """Chiamato all'avvio dello spider. Inizializza storage, buffer e contatori."""
        self.spider_name = spider.name
        self._buffers = {}
        self._batch_counts = {}
        self._total_batches = 0
        self.storage.init()
        logger.info(f"{self.__class__.__name__}: attiva (storage={self.storage.backend})")

    def close_spider(self, spider):
        """Chiamato alla chiusura dello spider. Salva gli item rimasti nei buffer come ultimi batch."""
        for category in list(self._buffers):
            if self._buffers[category]:
                self._flush_batch(category)
        logger.info(f"{self.__class__.__name__}: {self._total_batches} batch salvati ({dict(self._batch_counts)})")

    def process_item(self, item, spider):
        """
        Processa ogni item prodotto dallo spider.

        Ogni category ha il proprio buffer indipendente.
        Il flush avviene solo quando il buffer di quella category raggiunge batch_size.
        """
        event_data = self._item_to_dict(item)
        meta = ItemAdapter(item).get("meta") or {}
        source = (meta.get("source") or "").lower()
        category = (meta.get("category") or "default").lower()
        city_key = (meta.get("city_key") or "").lower()

        # Chiave buffer per il filename:
        # - puglia_culture: usa category (evento, spettacolo, rassegna)
        # - city_today: usa city_key (milano, roma, ecc.)
        # - altri spider: "default" (un solo buffer)
        if city_key:
            buffer_key = city_key
        elif source == "puglia_culture":
            buffer_key = category
        else:
            buffer_key = "default"

        if buffer_key not in self._buffers:
            self._buffers[buffer_key] = []

        self._buffers[buffer_key].append(event_data)

        if len(self._buffers[buffer_key]) >= self.batch_size:
            self._flush_batch(buffer_key)

        return item

    def _build_batch_filename(self, category: str, batch_num: int) -> str:
        """Genera il nome file per il batch."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if category == "default":
            return f"{self.spider_name}_{timestamp}_batch_{batch_num:03d}.json"
        return f"{self.spider_name}_{category}_{timestamp}_batch_{batch_num:03d}.json"

    def _flush_batch(self, category: str):
        """Salva il buffer della category come file JSON e svuota il buffer."""
        items = self._buffers.get(category, [])
        if not items:
            return

        self._batch_counts[category] = self._batch_counts.get(category, 0) + 1
        batch_num = self._batch_counts[category]
        self._total_batches += 1

        filename = self._build_batch_filename(category, batch_num)

        # Prefix: {dag_id}_{run_id_short} se disponibile, altrimenti batch/{spider}
        dag_id = os.environ.get('DAG_ID', '')
        dag_run_id = os.environ.get('DAG_RUN_ID', '')
        if dag_id and dag_run_id:
            # Abbrevia run_id: "manual__2026-03-18T22:33:49.355945+00:00" → "manual__2026-03-18T22:33"
            short_run_id = dag_run_id[:dag_run_id.find(':', 11) + 3] if ':' in dag_run_id else dag_run_id
            prefix = f"{dag_id}_{short_run_id}"
        else:
            prefix = f"batch/{self.spider_name}"

        # batch_file con path relativo: {prefix}/{filename}
        self._last_batch_file = f"{prefix}/{filename}"

        payload = {
            "spider": self.spider_name,
            "category": category,
            "batch": batch_num,
            "count": len(items),
            "sent_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "storage_path": self._last_batch_file,
            "events": items,
        }

        self.storage.save_json(filename, payload, prefix=prefix)
        self._buffers[category] = []

    def _item_to_dict(self, item) -> Dict[str, Any]:
        """Converte EventItem nel formato dict per il JSON di output."""
        adapter = ItemAdapter(item)
        result = {
            "uuid": adapter.get("uuid"),
            "title": adapter.get("title"),
            "meta": adapter.get("meta"),
        }
        if adapter.get("data"):
            result["data"] = adapter.get("data")
        return result


class ApiPipeline(BatchExportPipeline):
    """
    Pipeline per invio eventi all'API del backoffice.

    Eredita da BatchExportPipeline tutto: buffering, category tracking, salvataggio JSON.
    Aggiunge solo: autenticazione OAuth2 + invio HTTP dopo ogni _flush_batch.

    Flusso per ogni batch:
    1. Salva JSON su disco/MinIO (ereditato da _flush_batch)
    2. Invia lo stesso batch all'endpoint /api/external/v1/staging/bulk/
    """

    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        token_url: str,
        batch_size: int = 50,
        timeout: int = 30,
        storage_backend: str = "local",
    ):
        super().__init__(batch_size=batch_size, storage_backend=storage_backend)
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.timeout = timeout

        self.access_token: Optional[str] = None
        self.session = self._create_session()

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            base_url=crawler.settings.get("API_BASE_URL", "http://localhost:8000"),
            client_id=crawler.settings.get("API_CLIENT_ID", ""),
            client_secret=crawler.settings.get("API_CLIENT_SECRET", ""),
            token_url=crawler.settings.get(
                "KEYCLOAK_TOKEN_URL",
                "http://keycloak:8080/realms/today-events/protocol/openid-connect/token",
            ),
            batch_size=crawler.settings.getint("API_BATCH_SIZE", 50),
            timeout=crawler.settings.getint("API_TIMEOUT", 30),
            storage_backend=crawler.settings.get("STORAGE_BACKEND", "local"),
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

        try:
            response = self.session.post(
                self.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "openid read write",
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

    def open_spider(self, spider):
        """Inizializza pipeline: storage + autenticazione OAuth2."""
        super().open_spider(spider)
        logger.info(f"ApiPipeline: connessione a {self.base_url}")

        if not self.client_id or not self.client_secret:
            with tracer.start_as_current_span("scraper.pipeline_error", context=airflow_context) as span:
                span.set_attribute("error.type", "config")
                span.set_attribute("error.message", "API_CLIENT_ID o API_CLIENT_SECRET non configurati")
                from opentelemetry.trace import StatusCode
                span.set_status(StatusCode.ERROR, "Credenziali OAuth2 mancanti")
            raise CloseSpider("API_CLIENT_ID o API_CLIENT_SECRET non configurati")
        if not self._get_access_token():
            with tracer.start_as_current_span("scraper.pipeline_error", context=airflow_context) as span:
                span.set_attribute("error.type", "auth")
                span.set_attribute("error.message", "Impossibile ottenere token OAuth2")
                from opentelemetry.trace import StatusCode
                span.set_status(StatusCode.ERROR, "Token OAuth2 non ottenuto")
            raise CloseSpider("Impossibile ottenere token OAuth2 — controlla credenziali e che il backoffice sia attivo")

    def close_spider(self, spider):
        """Flush finale + chiude la sessione HTTP."""
        super().close_spider(spider)
        self.session.close()
        logger.info("ApiPipeline: connessione chiusa")

    def _flush_batch(self, category: str):
        """Salva JSON su disco (super) e invia lo stesso batch all'API."""
        # Salva una copia degli eventi prima che super() svuoti il buffer
        events = list(self._buffers.get(category, []))
        batch_num = self._batch_counts.get(category, 0) + 1

        # Salva JSON su disco/MinIO (imposta anche self._last_batch_file)
        super()._flush_batch(category)

        # Invia all'API con tracing OTel
        if not events:
            return

        batch_file = getattr(self, '_last_batch_file', '')
        ctx = airflow_context if airflow_context else None
        with tracer.start_as_current_span(
            "scraper.send_batch",
            context=ctx,
            attributes={
                "spider.name": self.spider_name,
                "batch.size": len(events),
                "batch.number": batch_num,
                "batch.category": category,
                "batch.file": batch_file,
            },
        ) as span:
            success = self._send_to_api(events, span, batch_file)
            if not success:
                raise CloseSpider(f"Invio batch fallito — {len(events)} eventi non inviati")

    def _send_to_api(self, events: List[Dict[str, Any]], span, batch_file: str = "") -> bool:
        """Invia batch all'endpoint bulk dell'API."""
        if not self.access_token:
            if not self._get_access_token():
                logger.error("Impossibile ottenere token, batch non inviato")
                span.set_attribute("batch.error", "token_failure")
                return False

        bulk_url = f"{self.base_url}/api/external/v1/staging/bulk/"

        try:
            payload = {"events": events, "spider": self.spider_name}
            if batch_file:
                payload["batch_file"] = batch_file

            response = self.session.post(
                bulk_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )

            span.set_attribute("http.status_code", response.status_code)

            if response.status_code == 201:
                result = response.json()
                logger.info(f"Batch inviato (sync): {result.get('created_count', 0)} eventi creati")
                return True

            elif response.status_code == 202:
                result = response.json()
                task_id = result.get('task_id', 'unknown')
                logger.info(f"Batch accettato (async): task_id={task_id}, {len(events)} eventi")
                span.set_attribute("celery.task_id", task_id)
                return True

            elif response.status_code == 401:
                logger.warning("Token scaduto, rinnovo...")
                self.access_token = None
                if self._get_access_token():
                    return self._send_to_api(events, span, batch_file)
                return False

            else:
                logger.error(f"Errore invio batch: {response.status_code} - {response.text}")
                span.set_attribute("batch.error", f"http_{response.status_code}")
                return False

        except requests.RequestException as e:
            logger.error(f"Errore richiesta API: {e}")
            span.set_attribute("batch.error", str(e))
            return False
