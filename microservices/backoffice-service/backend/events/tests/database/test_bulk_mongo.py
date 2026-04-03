# -*- coding: utf-8 -*-
"""
Test scraping → MongoDB.

Verifica che la pipeline di ingestione bulk (API sincrona, API asincrona)
scriva su MongoDB i documenti nel formato corretto e NON scriva su Postgres.

Pattern di mock:
- `events.mongo_repository.upsert_events` viene sostituito con una funzione
  che cattura i documenti ricevuti, permettendo di verificare la struttura.
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework import status

from events.models import Event
from events.tasks import process_bulk_events
from events.tests.helpers import (
    ExternalAPITestCase,
    event_minimal_payload,
    puglia_culture_payload,
)

BULK_URL = "/api/v1/events/bulk/"


# =============================================================================
# Helper
# =============================================================================

class _CaptureUpsert:
    """Context manager che rimpiazza upsert_events e cattura i documenti."""

    def __init__(self, test_case: TestCase):
        self._tc = test_case
        self.docs: list[dict] = []
        self._patcher = patch(
            "events.mongo_repository.upsert_events",
            side_effect=self._capture,
        )

    def _capture(self, docs: list[dict]) -> int:
        self.docs.extend(docs)
        return len(docs)

    def __enter__(self):
        self._patcher.start()
        self._tc.addCleanup(self._patcher.stop)
        return self

    def __exit__(self, *args):
        pass


# =============================================================================
# Test task Celery (asincrono)
# =============================================================================

class ProcessBulkEventsMongoTaskTest(TestCase):
    """process_bulk_events scrive su MongoDB, non su Postgres."""

    def test_task_scrive_evento_puglia_su_mongodb(self):
        """Il task Celery scrive il documento su MongoDB partendo dal payload nested di puglia_culture."""
        with _CaptureUpsert(self) as capture:
            result = process_bulk_events(
                [puglia_culture_payload(uuid="task-puglia-001")],
                spider_name="puglia_culture",
            )

        self.assertEqual(result["created_count"], 1)
        self.assertEqual(result["failed_count"], 0)
        self.assertEqual(len(capture.docs), 1)

    def test_documento_ha_campi_flat(self):
        """Il documento MongoDB ha i campi flat estratti dal payload nested."""
        with _CaptureUpsert(self) as capture:
            process_bulk_events(
                [puglia_culture_payload(uuid="task-flat-001")],
                spider_name="puglia_culture",
            )

        doc = capture.docs[0]
        self.assertEqual(doc["uuid"], "task-flat-001")
        self.assertEqual(doc["source"], "puglia_culture")
        self.assertEqual(doc["city"], "Lecce")
        self.assertEqual(doc["location_name"], "Teatro Paisiello")
        self.assertEqual(doc["category"], ["teatro", "spettacolo"])
        self.assertEqual(doc["spider"], "puglia_culture")
        self.assertEqual(doc["status"], "staging")
        self.assertTrue(doc["is_active"])

    def test_documento_ha_raw_originale(self):
        """Il documento MongoDB contiene il campo _raw con il payload originale dello spider."""
        payload = puglia_culture_payload(uuid="task-raw-001")
        with _CaptureUpsert(self) as capture:
            process_bulk_events([payload], spider_name="puglia_culture")

        doc = capture.docs[0]
        self.assertIn("_raw", doc)
        # _raw deve contenere la struttura nested originale
        self.assertIn("data", doc["_raw"])
        self.assertIn("meta", doc["_raw"])
        self.assertEqual(doc["_raw"]["meta"]["source"], "puglia_culture")
        self.assertEqual(doc["_raw"]["data"]["city"]["city_name"], "Lecce")

    def test_nessuna_scrittura_su_postgres(self):
        """Il task NON scrive nulla sulla tabella Postgres Event."""
        with _CaptureUpsert(self):
            process_bulk_events(
                [puglia_culture_payload(uuid="task-nopg-001")],
                spider_name="puglia_culture",
            )

        self.assertEqual(Event.objects.count(), 0)

    def test_batch_multipli_eventi_puglia(self):
        """Un batch di più eventi Puglia viene scritto su MongoDB correttamente."""
        payloads = [
            puglia_culture_payload(uuid=f"task-batch-{i}", title=f"Spettacolo {i}")
            for i in range(5)
        ]
        with _CaptureUpsert(self) as capture:
            result = process_bulk_events(payloads, spider_name="puglia_culture")

        self.assertEqual(result["created_count"], 5)
        self.assertEqual(len(capture.docs), 5)
        uuids = {doc["uuid"] for doc in capture.docs}
        self.assertEqual(uuids, {f"task-batch-{i}" for i in range(5)})

    def test_evento_non_valido_non_viene_scritto(self):
        """Un evento senza titolo non viene scritto su MongoDB."""
        payloads = [
            puglia_culture_payload(uuid="task-valid-001"),
            {"uuid": "task-invalid-001", "meta": {"source": "puglia_culture"}},  # manca title
        ]
        with _CaptureUpsert(self) as capture:
            result = process_bulk_events(payloads, spider_name="puglia_culture")

        self.assertEqual(result["created_count"], 1)
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(len(capture.docs), 1)
        self.assertEqual(capture.docs[0]["uuid"], "task-valid-001")

    def test_retry_su_errore_mongodb(self):
        """Il task esegue retry se upsert_events solleva un'eccezione."""
        with patch(
            "events.mongo_repository.upsert_events",
            side_effect=Exception("MongoDB down"),
        ), patch.object(
            process_bulk_events,
            "retry",
            side_effect=RuntimeError("retry-called"),
        ) as mock_retry:
            with self.assertRaisesMessage(RuntimeError, "retry-called"):
                process_bulk_events(
                    [puglia_culture_payload(uuid="task-retry-001")],
                    spider_name="puglia_culture",
                )

        mock_retry.assert_called_once()


# =============================================================================
# Test API sincrona (?sync=true)
# =============================================================================

class BulkSyncMongoTest(ExternalAPITestCase):
    """POST /api/v1/events/bulk/?sync=true → scrive su MongoDB, non Postgres."""

    def test_sync_scrive_evento_puglia_su_mongodb(self):
        """La bulk sincrona scrive l'evento su MongoDB."""
        self.authenticate_consumer(actions=("read", "create"))
        with _CaptureUpsert(self) as capture:
            response = self.client.post(
                f"{BULK_URL}?sync=true",
                data={"events": [puglia_culture_payload(uuid="sync-puglia-001")], "spider": "puglia_culture"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["created_count"], 1)
        self.assertEqual(len(capture.docs), 1)

    def test_sync_documento_ha_campi_flat(self):
        """La bulk sincrona produce un documento con campi flat corretti."""
        self.authenticate_consumer(actions=("read", "create"))
        with _CaptureUpsert(self) as capture:
            self.client.post(
                f"{BULK_URL}?sync=true",
                data={"events": [puglia_culture_payload(uuid="sync-flat-001")], "spider": "puglia_culture"},
                format="json",
            )

        doc = capture.docs[0]
        self.assertEqual(doc["uuid"], "sync-flat-001")
        self.assertEqual(doc["source"], "puglia_culture")
        self.assertEqual(doc["city"], "Lecce")
        self.assertEqual(doc["location_name"], "Teatro Paisiello")
        self.assertEqual(doc["category"], ["teatro", "spettacolo"])
        self.assertEqual(doc["status"], "staging")

    def test_sync_documento_ha_raw_originale(self):
        """La bulk sincrona preserva il payload nested originale in _raw."""
        self.authenticate_consumer(actions=("read", "create"))
        payload = puglia_culture_payload(uuid="sync-raw-001")
        with _CaptureUpsert(self) as capture:
            self.client.post(
                f"{BULK_URL}?sync=true",
                data={"events": [payload], "spider": "puglia_culture"},
                format="json",
            )

        doc = capture.docs[0]
        self.assertIn("_raw", doc)
        self.assertEqual(doc["_raw"]["meta"]["source"], "puglia_culture")
        self.assertEqual(doc["_raw"]["data"]["city"]["city_name"], "Lecce")

    def test_sync_nessuna_scrittura_su_postgres(self):
        """La bulk sincrona NON scrive sulla tabella Postgres Event."""
        self.authenticate_consumer(actions=("read", "create"))
        with _CaptureUpsert(self):
            self.client.post(
                f"{BULK_URL}?sync=true",
                data={"events": [puglia_culture_payload(uuid="sync-nopg-001")]},
                format="json",
            )

        self.assertEqual(Event.objects.count(), 0)

    def test_sync_risposta_contiene_uuid_e_titolo(self):
        """La risposta della bulk sincrona include uuid e titolo degli eventi scritti."""
        self.authenticate_consumer(actions=("read", "create"))
        with _CaptureUpsert(self):
            response = self.client.post(
                f"{BULK_URL}?sync=true",
                data={"events": [puglia_culture_payload(uuid="sync-resp-001")]},
                format="json",
            )

        self.assertEqual(len(response.data["successful_events"]), 1)
        ev = response.data["successful_events"][0]
        self.assertEqual(ev["uuid"], "sync-resp-001")
        self.assertIn("title", ev)

    def test_sync_partial_failure_su_batch_misto(self):
        """Un batch misto restituisce successi e fallimenti separati."""
        self.authenticate_consumer(actions=("read", "create"))
        with _CaptureUpsert(self) as capture:
            response = self.client.post(
                f"{BULK_URL}?sync=true",
                data={
                    "events": [
                        puglia_culture_payload(uuid="sync-mix-ok"),
                        {"uuid": "sync-mix-fail", "meta": {"source": "puglia_culture"}},
                    ]
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["created_count"], 1)
        self.assertEqual(response.data["failed_count"], 1)
        self.assertEqual(len(capture.docs), 1)

    def test_sync_errore_mongodb_restituisce_bad_request(self):
        """Se upsert_events fallisce, la bulk sincrona restituisce 400."""
        self.authenticate_consumer(actions=("read", "create"))
        with patch("events.mongo_repository.upsert_events", side_effect=Exception("mongo down")):
            response = self.client.post(
                f"{BULK_URL}?sync=true",
                data={"events": [puglia_culture_payload(uuid="sync-err-001")]},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["created_count"], 0)


# =============================================================================
# Test API asincrona (default)
# =============================================================================

class BulkAsyncMongoTest(ExternalAPITestCase):
    """POST /api/v1/events/bulk/ (async) → dispatcha il task Celery."""

    def test_async_dispatcha_task_celery(self):
        """La bulk asincrona dispatcha process_bulk_events con spider_name=puglia_culture."""
        mock_task = MagicMock()
        mock_task.id = "task-puglia-async-001"
        self.authenticate_consumer(actions=("read", "create"))

        with patch("events.tasks.process_bulk_events.apply_async", return_value=mock_task) as mock_apply:
            response = self.client.post(
                BULK_URL,
                data={
                    "events": [puglia_culture_payload(uuid="async-puglia-001")],
                    "spider": "puglia_culture",
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["task_id"], "task-puglia-async-001")
        call_kwargs = mock_apply.call_args[1]["kwargs"]
        self.assertEqual(call_kwargs["spider_name"], "puglia_culture")

    def test_async_payload_passato_al_task(self):
        """Il payload degli eventi viene passato correttamente al task Celery."""
        mock_task = MagicMock()
        mock_task.id = "task-payload-check"
        self.authenticate_consumer(actions=("read", "create"))
        payload = puglia_culture_payload(uuid="async-payload-001")

        with patch("events.tasks.process_bulk_events.apply_async", return_value=mock_task) as mock_apply:
            self.client.post(
                BULK_URL,
                data={"events": [payload], "spider": "puglia_culture"},
                format="json",
            )

        args_passed = mock_apply.call_args[1]["args"][0]
        self.assertEqual(len(args_passed), 1)
        self.assertEqual(args_passed[0]["uuid"], "async-payload-001")
        self.assertEqual(args_passed[0]["meta"]["source"], "puglia_culture")
