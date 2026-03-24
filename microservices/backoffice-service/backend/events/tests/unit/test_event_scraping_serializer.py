from django.test import TestCase

from events.serializers import EventScrapingSerializer
from events.tests.helpers import event_minimal_payload, event_scraping_payload


class EventScrapingSerializerTest(TestCase):
    def test_required_fields_are_enforced(self):
        serializer = EventScrapingSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn("uuid", serializer.errors)
        self.assertIn("source", serializer.errors)
        self.assertIn("title", serializer.errors)

    def test_nested_city_and_dates_are_flattened(self):
        serializer = EventScrapingSerializer(data=event_scraping_payload())
        serializer.is_valid(raise_exception=True)

        self.assertEqual(serializer.validated_data["city"], "Milano")
        self.assertEqual(serializer.validated_data["location_name"], "Blue Note")
        self.assertEqual(serializer.validated_data["location_address"], "Via Borsieri 37")
        self.assertEqual(serializer.validated_data["date_start"].strftime("%Y-%m-%d"), "2026-06-15")
        self.assertEqual(serializer.validated_data["date_end"].strftime("%Y-%m-%d"), "2026-06-15")

    def test_invalid_coordinates_are_ignored(self):
        payload = event_scraping_payload()
        payload["city"]["location_coords"] = {"lat": "bad", "lng": "coords"}
        serializer = EventScrapingSerializer(data=payload)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.validated_data["location_coordinates"])

    def test_optional_empty_strings_become_none(self):
        serializer = EventScrapingSerializer(
            data=event_minimal_payload(url="", description="", image_url="", price="")
        )
        serializer.is_valid(raise_exception=True)

        self.assertIsNone(serializer.validated_data["url"])
        self.assertIsNone(serializer.validated_data["description"])
        self.assertIsNone(serializer.validated_data["image_url"])
        self.assertIsNone(serializer.validated_data["price"])

    def test_raw_data_preserves_original_payload(self):
        payload = event_scraping_payload()
        serializer = EventScrapingSerializer(data=payload)
        serializer.is_valid(raise_exception=True)

        self.assertEqual(serializer.validated_data["raw_data"]["uuid"], payload["uuid"])
        self.assertEqual(serializer.validated_data["raw_data"]["title"], payload["title"])
