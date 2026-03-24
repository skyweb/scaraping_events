from django.test import TestCase

from events.models import Event
from events.serializers import EventScrapingSerializer
from events.tests.helpers import event_scraping_payload


class BulkIngestionRegressionTest(TestCase):
    def test_upsert_by_uuid_does_not_duplicate_event(self):
        payload = event_scraping_payload(uuid="dup-001", title="Versione 1")

        serializer = EventScrapingSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        payload["title"] = "Versione 2"
        serializer = EventScrapingSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        self.assertEqual(Event.objects.filter(uuid="dup-001").count(), 1)
        self.assertEqual(Event.objects.get(uuid="dup-001").title, "Versione 2")

    def test_nested_spider_format_preserves_batch_file(self):
        payload = {
            "uuid": "nested-001",
            "title": "Evento spider",
            "meta": {
                "source": "nested_spider",
                "content_hash": "hash-nested",
                "url": "https://example.com/nested",
                "scraped_at": "2026-06-01T10:00:00Z",
                "batch_file": "nested/batch.json",
            },
            "data": {
                "description": "Evento nested",
                "category": ["musica"],
                "city": {"city_name": "Milano"},
                "dates": {"date_start": "2026-06-15"},
            },
        }

        serializer = EventScrapingSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        event = serializer.save()

        self.assertEqual(event.batch_file, "nested/batch.json")
        self.assertEqual(event.raw_data["data"]["description"], "Evento nested")
