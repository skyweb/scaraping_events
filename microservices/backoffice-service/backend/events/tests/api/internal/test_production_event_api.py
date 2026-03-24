from rest_framework import status

from events.models import Event
from events.tests.helpers import InternalAPITestCase


class ProductionEventViewSetTest(InternalAPITestCase):
    def test_internal_list_returns_only_published_events(self):
        """Verifica che la lista interna restituisca solo gli eventi pubblicati."""
        self.create_event(uuid="pub-001", status=Event.Status.PUBLISHED)
        self.create_staging_event(uuid="stg-001")

        response = self.client.get("/api/events/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        uuids = {item["uuid"] for item in response.data["results"]}
        self.assertIn("pub-001", uuids)
        self.assertNotIn("stg-001", uuids)

    def test_toggle_active_flips_flag(self):
        """Verifica che la funzione toggle_active inverta il flag del parametro is_active."""
        event = self.create_event(uuid="toggle-001", is_active=True)

        response = self.client.post(f"/api/events/{event.pk}/toggle_active/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event.refresh_from_db()
        self.assertFalse(event.is_active)

    def test_cities_returns_aggregated_counts(self):
        """Verifica che l'endpoint delle città restituisca conteggi aggregati per città."""
        self.create_event(uuid="city-count-001", city="Roma")
        self.create_event(uuid="city-count-002", city="Roma")
        self.create_event(uuid="city-count-003", city="Milano")

        response = self.client.get("/api/events/cities/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["city"], "Roma")
        self.assertEqual(response.data[0]["count"], 2)

    def test_sources_returns_aggregated_counts(self):
        """Verifica che l'endpoint delle fonti restituisca conteggi aggregati per fonte."""
        self.create_event(uuid="source-count-001", source="feed-a")
        self.create_event(uuid="source-count-002", source="feed-a")
        self.create_event(uuid="source-count-003", source="feed-b")

        response = self.client.get("/api/events/sources/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["source"], "feed-a")
        self.assertEqual(response.data[0]["count"], 2)

    def test_dashboard_returns_aggregated_counts(self):
        """Verifica che la dashboard restituisca i conteggi aggregati totali."""
        self.create_event(uuid="dash-001", city="Roma", source="source-a")
        self.create_event(uuid="dash-002", city="Roma", source="source-a", is_active=False)
        self.create_staging_event(uuid="dash-stg-001")

        response = self.client.get("/api/dashboard/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_events"], 2)
        self.assertEqual(response.data["active_events"], 1)
        self.assertEqual(response.data["staging_count"], 1)
