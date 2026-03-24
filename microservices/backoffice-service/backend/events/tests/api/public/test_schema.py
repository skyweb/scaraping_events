from django.test import TestCase
from drf_spectacular.generators import SchemaGenerator


class PublicOpenAPISchemaTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.schema = SchemaGenerator().get_schema(request=None, public=True)

    def test_schema_contains_public_event_paths(self):
        paths = self.schema.get("paths", {})
        self.assertIn("/api/v1/events/", paths)
        self.assertIn("/api/v1/events/{id}/", paths)
        self.assertIn("/api/v1/events/bulk/", paths)
        self.assertIn("/api/v1/events/bulk-status/{task_id}/", paths)

    def test_create_operation_has_examples(self):
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
