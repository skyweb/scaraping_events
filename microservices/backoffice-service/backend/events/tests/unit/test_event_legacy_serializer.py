from django.test import TestCase

from events.serializers import EventLegacySerializer
from events.tests.helpers import event_legacy_payload


class EventLegacySerializerTest(TestCase):
    def test_legacy_payload_is_normalized(self):
        serializer = EventLegacySerializer(data=event_legacy_payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)

        self.assertEqual(serializer.validated_data["location_name"], "Palazzo Reale")
        self.assertEqual(serializer.validated_data["location_address"], "Piazza Duomo 12, Milano")
        self.assertEqual(serializer.validated_data["date_start"].strftime("%Y-%m-%d"), "2026-06-01")
        self.assertEqual(serializer.validated_data["date_end"].strftime("%Y-%m-%d"), "2026-08-31")
        self.assertEqual(len(serializer.validated_data["uuid"]), 32)
        self.assertEqual(len(serializer.validated_data["content_hash"]), 32)

    def test_csv_category_is_split(self):
        payload = event_legacy_payload()
        payload["list"]["category"] = "arte, mostre, cultura"
        serializer = EventLegacySerializer(data=payload)
        serializer.is_valid(raise_exception=True)

        self.assertEqual(serializer.validated_data["category"], ["arte", "mostre", "cultura"])

    def test_required_fields_are_enforced(self):
        serializer = EventLegacySerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn("title", serializer.errors)
        self.assertIn("source", serializer.errors)
