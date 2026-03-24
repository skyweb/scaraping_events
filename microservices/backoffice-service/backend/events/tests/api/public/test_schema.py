from django.test import TestCase
from drf_spectacular.generators import SchemaGenerator


class PublicOpenAPISchemaTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Configura i pesi e i dati di test iniziali validi per tutti i test."""
        cls.schema = SchemaGenerator().get_schema(request=None, public=True)

    def test_schema_contains_public_event_paths(self):
        """Verifica che lo schema contenga i percorsi API corretti degli eventi pubblici."""
        paths = self.schema.get("paths", {})
        self.assertIn("/api/v1/events/", paths)
        self.assertIn("/api/v1/events/{id}/", paths)
        self.assertIn("/api/v1/events/bulk/", paths)
        self.assertIn("/api/v1/events/bulk-status/{task_id}/", paths)

    def test_create_operation_has_examples(self):
        """Verifica che l'operazione di creazione evento abbia degli esempi validi di payload."""
        examples = (
            self.schema["paths"]["/api/v1/events/"]["post"]["requestBody"]["content"]["application/json"]["examples"]
        )
        self.assertGreaterEqual(len(examples), 2)

        normalized_keys = {
            key.replace(" ", "").replace("-", "").replace("_", "").lower()
            for key in examples.keys()
        }
        self.assertIn("eventocompleto", normalized_keys)
        self.assertIn("eventominimo", normalized_keys)
