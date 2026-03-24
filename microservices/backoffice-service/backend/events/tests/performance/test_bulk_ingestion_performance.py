from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from events.tasks import process_bulk_events
from events.tests.helpers import event_minimal_payload


class BulkIngestionPerformanceTest(TestCase):
    def test_bulk_task_keeps_query_count_bounded(self):
        """Verifica che l'ingestione massiva limiti ed ottimizzi il numero massimo di query effettuate (escludendo il problema n+1)."""
        events = [
            event_minimal_payload(uuid=f"perf-{index:03d}", title=f"Evento {index}")
            for index in range(25)
        ]

        with CaptureQueriesContext(connection) as queries:
            result = process_bulk_events(events, spider_name="perf_spider")

        self.assertEqual(result["created_count"], 25)
        self.assertLessEqual(len(queries), 2)
