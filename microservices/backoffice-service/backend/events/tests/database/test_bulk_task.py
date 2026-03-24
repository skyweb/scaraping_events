from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase

from events.models import Event
from events.tasks import process_bulk_events
from events.tests.helpers import event_minimal_payload, event_scraping_payload


class ProcessBulkEventsTaskTest(TestCase):
    def test_creates_all_valid_events(self):
        """Verifica la corretta creazione masiva di tutti gli eventi validi forniti."""
        events = [
            event_minimal_payload(uuid=f"task-ok-{index}", title=f"Evento {index}")
            for index in range(5)
        ]

        result = process_bulk_events(events, spider_name="test_spider")

        self.assertEqual(result["created_count"], 5)
        self.assertEqual(result["failed_count"], 0)
        self.assertEqual(Event.objects.filter(source="test_spider").count(), 5)

    def test_mixed_batch_reports_failed_indexes(self):
        """Verifica che in un lotto (batch) misto vengano segnalati correttamente gli indici degli elementi falliti."""
        events = [
            event_minimal_payload(uuid="mix-ok-1", title="Valido 1"),
            {"uuid": "mix-fail-1", "source": "x"},
            event_minimal_payload(uuid="mix-ok-2", title="Valido 2"),
            {"source": "x", "title": "No UUID"},
        ]

        result = process_bulk_events(events, spider_name="test_spider")

        self.assertEqual(result["created_count"], 2)
        self.assertEqual(result["failed_count"], 2)
        self.assertEqual([item["index"] for item in result["failed_events"]], [1, 3])

    def test_handles_nested_scraping_payload(self):
        """Verifica la corretta acquisizione e gestione dei payload di scraping con dati annidati."""
        result = process_bulk_events(
            [event_scraping_payload(uuid="task-nested-001")],
            spider_name="test_spider",
        )

        self.assertEqual(result["created_count"], 1)
        event = Event.objects.get(uuid="task-nested-001")
        self.assertEqual(event.city, "Milano")
        self.assertEqual(event.location_name, "Blue Note")

    def test_falls_back_to_individual_saves_when_bulk_create_fails(self):
        """Verifica l'entrata in azione del fallback sui salvataggi singoli in caso di errore generico nel bulk_create."""
        with patch.object(
            Event.objects,
            "bulk_create",
            side_effect=Exception("Simulated bulk failure"),
        ):
            result = process_bulk_events(
                [event_minimal_payload(uuid="fallback-001", title="Fallback test")],
                spider_name="test_spider",
            )

        self.assertEqual(result["created_count"], 1)
        self.assertEqual(result["failed_count"], 0)
        self.assertTrue(Event.objects.filter(uuid="fallback-001").exists())

    def test_returns_only_failed_events_when_all_payloads_are_invalid(self):
        """Verifica che il risultato censisca come falliti tutti gli eventi, se interamente non validi in input."""
        result = process_bulk_events(
            [
                {"source": "test_spider"},
                {"uuid": "invalid-no-title", "source": "test_spider"},
            ],
            spider_name="test_spider",
        )

        self.assertEqual(result["created_count"], 0)
        self.assertEqual(result["failed_count"], 2)
        self.assertEqual([item["index"] for item in result["failed_events"]], [0, 1])
        self.assertFalse(Event.objects.exists())

    def test_retries_when_bulk_create_raises_operational_error(self):
        """Verifica che venga effettuato un ri-tentativo (retry) del task qualora il database non sia momentaneamente disponibile."""
        with patch.object(
            Event.objects,
            "bulk_create",
            side_effect=OperationalError("db unavailable"),
        ), patch.object(
            process_bulk_events,
            "retry",
            side_effect=RuntimeError("retry-called"),
        ) as mocked_retry:
            with self.assertRaisesMessage(RuntimeError, "retry-called"):
                process_bulk_events(
                    [event_minimal_payload(uuid="retry-001", title="Retry me")],
                    spider_name="test_spider",
                )

        mocked_retry.assert_called_once()

    def test_fallback_collects_save_failures(self):
        """Verifica che la modalità fallback intercetti sia i successi che i fallimenti d'inserimento singolo."""
        events = [
            event_minimal_payload(uuid="fallback-ok", title="Fallback ok"),
            event_minimal_payload(uuid="fallback-ko", title="Fallback ko"),
        ]

        with patch.object(
            Event.objects,
            "bulk_create",
            side_effect=Exception("Simulated bulk failure"),
        ), patch(
            "events.models.Event.save",
            autospec=True,
            side_effect=[None, Exception("save exploded")],
        ):
            result = process_bulk_events(events, spider_name="test_spider")

        self.assertEqual(result["created_count"], 1)
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(result["failed_events"][0]["index"], 1)
        self.assertEqual(
            result["failed_events"][0]["errors"]["non_field_errors"],
            ["save exploded"],
        )
