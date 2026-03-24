from unittest.mock import MagicMock, patch

from rest_framework import status

from events.views import ExternalEventViewSet
from events.models import Event
from events.tests.helpers import ExternalAPITestCase, event_legacy_payload, event_minimal_payload, event_scraping_payload


class ExternalBulkIngestionTest(ExternalAPITestCase):
    BULK_URL = "/api/v1/events/bulk/"

    def test_sync_bulk_accepts_scraping_and_legacy_formats(self):
        """Verifica che l'ingestione massiva sincrona accetti formati di scraping e antichi (legacy)."""
        self.authenticate_consumer(actions=("read", "create"))

        response = self.client.post(
            f"{self.BULK_URL}?sync=true",
            data={
                "events": [
                    event_scraping_payload(uuid="mix-new-001"),
                    event_legacy_payload(title="Evento Legacy Mix"),
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["created_count"], 2)

    def test_sync_bulk_returns_partial_success_payload(self):
        """Verifica che l'ingestione massiva sincrona restituisca un payload indicando i successi e i fallimenti parziali."""
        self.authenticate_consumer(actions=("read", "create"))

        response = self.client.post(
            f"{self.BULK_URL}?sync=true",
            data={
                "events": [
                    event_minimal_payload(uuid="ok-001"),
                    {"uuid": "fail-001", "source": "test_spider"},
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["created_count"], 1)
        self.assertEqual(response.data["failed_count"], 1)
        self.assertEqual(response.data["failed_events"][0]["index"], 1)

    def test_async_bulk_dispatches_task(self):
        """Verifica che l'ingestione massiva asincrona avvii correttamente il task in background."""
        task_result = MagicMock()
        task_result.id = "async-task-001"
        self.authenticate_consumer(actions=("read", "create"))

        with patch("events.tasks.process_bulk_events.apply_async", return_value=task_result) as mocked_apply:
            response = self.client.post(
                self.BULK_URL,
                data={"events": [event_minimal_payload(uuid="async-001")], "spider": "puglia_culture"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["task_id"], "async-task-001")
        self.assertEqual(mocked_apply.call_args[1]["kwargs"]["spider_name"], "puglia_culture")

    def test_bulk_requires_events_payload(self):
        """Verifica che l'endpoint bulk richieda obbligatoriamente il campo events nel payload."""
        self.authenticate_consumer(actions=("read", "create"))

        response = self.client.post(self.BULK_URL, data={"events": []}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], 'No events provided. Expected {"events": [...]}')

    def test_bulk_injects_batch_file_into_raw_payload(self):
        """Verifica che l'ingestione massiva inserisca il riferimento al file batch nel payload originario."""
        self.authenticate_consumer(actions=("read", "create"))

        response = self.client.post(
            f"{self.BULK_URL}?sync=true",
            data={
                "batch_file": "imports/2026-03-24/events.json",
                "events": [event_scraping_payload(uuid="batch-file-001")],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Event.objects.get(uuid="batch-file-001").batch_file, "imports/2026-03-24/events.json")

    def test_bulk_preserves_existing_event_batch_file(self):
        """Verifica che l'ingestione massiva preservi il batch file di un evento se già presente."""
        self.authenticate_consumer(actions=("read", "create"))

        response = self.client.post(
            f"{self.BULK_URL}?sync=true",
            data={
                "batch_file": "imports/2026-03-24/events.json",
                "events": [
                    {
                        **event_scraping_payload(uuid="batch-existing-001"),
                        "meta": {"batch_file": "already-set.json"},
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Event.objects.get(uuid="batch-existing-001").batch_file, "already-set.json")

    def test_sync_bulk_returns_bad_request_when_all_saves_fail(self):
        """Verifica che un'ingestione massiva sincrona ritorni un errore Bad Request quando tutti i salvataggi falliscono."""
        self.authenticate_consumer(actions=("read", "create"))

        with patch("events.views.EventScrapingSerializer.save", side_effect=Exception("save failed")):
            response = ExternalEventViewSet()._bulk_sync([event_minimal_payload(uuid="sync-fail-001")])

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["created_count"], 0)
        self.assertEqual(response.data["failed_count"], 1)
        self.assertEqual(response.data["failed_events"][0]["index"], 0)

    def test_bulk_status_endpoint_returns_task_state(self):
        """Verifica che l'endpoint di stato asincrono restituisca correttamente lo stato di un task concluso."""
        mock_result = MagicMock()
        mock_result.status = "SUCCESS"
        mock_result.ready.return_value = True
        mock_result.successful.return_value = True
        mock_result.result = {"created_count": 2, "failed_count": 0, "failed_events": []}
        self.authenticate_consumer(actions=("read",))

        with patch("events.views.AsyncResult", return_value=mock_result):
            response = self.client.get("/api/v1/events/bulk-status/task-123/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "SUCCESS")
        self.assertEqual(response.data["result"]["created_count"], 2)

    def test_bulk_status_endpoint_returns_pending_state(self):
        """Verifica che l'endpoint di stato restituista uno stato pending per un task in attesa."""
        mock_result = MagicMock()
        mock_result.status = "PENDING"
        mock_result.ready.return_value = False
        self.authenticate_consumer(actions=("read",))

        with patch("events.views.AsyncResult", return_value=mock_result):
            response = self.client.get("/api/v1/events/bulk-status/task-pending/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "PENDING")
        self.assertIsNone(response.data["result"])

    def test_bulk_status_endpoint_returns_failure_state(self):
        """Verifica che l'endpoint di stato restituisca un errore in caso di fallimento lato DB."""
        mock_result = MagicMock()
        mock_result.status = "FAILURE"
        mock_result.ready.return_value = True
        mock_result.successful.return_value = False
        mock_result.result = Exception("DB down")
        self.authenticate_consumer(actions=("read",))

        with patch("events.views.AsyncResult", return_value=mock_result):
            response = self.client.get("/api/v1/events/bulk-status/task-failure/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "FAILURE")
        self.assertIn("DB down", response.data["result"])

    def test_bulk_status_requires_read_permission(self):
        """Verifica che per controllare lo stato del bulk sia necessario il permesso di lettura."""
        self.authenticate_consumer(actions=("create",))

        response = self.client.get("/api/v1/events/bulk-status/task-no-read/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
