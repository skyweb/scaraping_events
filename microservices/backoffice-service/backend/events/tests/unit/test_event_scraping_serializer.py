from django.test import TestCase

from events.serializers import EventScrapingSerializer
from events.tests.helpers import event_minimal_payload, event_scraping_payload


class EventScrapingSerializerTest(TestCase):
    def test_required_fields_are_enforced(self):
        """Verifica che campi cardinali come uuid, source e title siano rigorosamente pretesi."""
        serializer = EventScrapingSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn("uuid", serializer.errors)
        self.assertIn("source", serializer.errors)
        self.assertIn("title", serializer.errors)

    def test_nested_city_and_dates_are_flattened(self):
        """Verifica che sezioni e strutture dati annidate (città, date) vengano estratte, de-gerarchizzate e normalizzate."""
        serializer = EventScrapingSerializer(data=event_scraping_payload())
        serializer.is_valid(raise_exception=True)

        self.assertEqual(serializer.validated_data["city"], "Milano")
        self.assertEqual(serializer.validated_data["location_name"], "Blue Note")
        self.assertEqual(serializer.validated_data["location_address"], "Via Borsieri 37")
        self.assertEqual(serializer.validated_data["date_start"].strftime("%Y-%m-%d"), "2026-06-15")
        self.assertEqual(serializer.validated_data["date_end"].strftime("%Y-%m-%d"), "2026-06-15")

    def test_invalid_coordinates_are_ignored(self):
        """Verifica che coordinate irriconoscibili o errate vengano escluse per ovviare ad eccezioni e cadute della validazione."""
        payload = event_scraping_payload()
        payload["city"]["location_coords"] = {"lat": "bad", "lng": "coords"}
        serializer = EventScrapingSerializer(data=payload)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.validated_data["location_coordinates"])

    def test_optional_empty_strings_become_none(self):
        """Verifica che valori opzionali passati in formato vuoto decadano in più coerenti valori None."""
        serializer = EventScrapingSerializer(
            data=event_minimal_payload(url="", description="", image_url="", price="")
        )
        serializer.is_valid(raise_exception=True)

        self.assertIsNone(serializer.validated_data["url"])
        self.assertIsNone(serializer.validated_data["description"])
        self.assertIsNone(serializer.validated_data["image_url"])
        self.assertIsNone(serializer.validated_data["price"])

    def test_raw_data_preserves_original_payload(self):
        """Verifica che il contenitore raw_data preservi in forma intonsa e storicizzata le sembianze originarie del payload."""
        payload = event_scraping_payload()
        serializer = EventScrapingSerializer(data=payload)
        serializer.is_valid(raise_exception=True)

        self.assertEqual(serializer.validated_data["raw_data"]["uuid"], payload["uuid"])
        self.assertEqual(serializer.validated_data["raw_data"]["title"], payload["title"])

    def test_partial_update_does_not_require_uuid_source_and_title(self):
        """Verifica che l'update parziale autorizzi transazioni omissive di campi nativamente reputati obbligatori."""
        serializer = EventScrapingSerializer(data={"description": "Test update"}, partial=True)
        serializer.is_valid(raise_exception=True)

        self.assertEqual(serializer.validated_data["description"], "Test update")
        self.assertNotIn("uuid", serializer.validated_data)

    def test_update_applies_validated_fields_to_instance(self):
        """Verifica che le variazioni vengano materializzate e scritte concretamente sull'istanza evento in fase di update."""
        from events.tests.factories import create_event

        event = create_event(uuid="serializer-update-001", title="Titolo iniziale")
        serializer = EventScrapingSerializer(
            instance=event,
            data={"title": "Titolo nuovo", "description": "Descrizione nuova"},
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()

        self.assertEqual(updated.title, "Titolo nuovo")
        self.assertEqual(updated.description, "Descrizione nuova")
