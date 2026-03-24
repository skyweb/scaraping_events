from rest_framework import status
from rest_framework.test import APIRequestFactory
from django.contrib.auth.models import AnonymousUser

from events.models import Event
from events.views import ExternalEventViewSet
from events.tests.factories import create_staff_user
from events.tests.helpers import ExternalAPITestCase, event_minimal_payload, event_scraping_payload


class ExternalEventCRUDTest(ExternalAPITestCase):
    def test_list_events(self):
        self.create_event(uuid="list-001")
        self.create_event(uuid="list-002", title="Evento 2")
        self.authenticate_consumer(actions=("read",))

        response = self.client.get("/api/v1/events/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["count"], 2)

    def test_list_can_filter_by_city(self):
        self.create_event(uuid="city-001", city="Roma")
        self.create_event(uuid="city-002", city="Milano")
        self.authenticate_consumer(actions=("read",))

        response = self.client.get("/api/v1/events/?city=Roma")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["uuid"], "city-001")

    def test_list_can_filter_by_source(self):
        self.create_event(uuid="source-001", source="source-a")
        self.create_event(uuid="source-002", source="source-b")
        self.authenticate_consumer(actions=("read",))

        response = self.client.get("/api/v1/events/?source=source-b")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["uuid"], "source-002")

    def test_list_can_search(self):
        self.create_event(uuid="search-001", title="Concerto Jazz al Blue Note")
        self.create_event(uuid="search-002", title="Mostra Rinascimentale")
        self.authenticate_consumer(actions=("read",))

        response = self.client.get("/api/v1/events/?search=Jazz")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["uuid"], "search-001")

    def test_list_can_order_by_city(self):
        self.create_event(uuid="order-001", city="Roma")
        self.create_event(uuid="order-002", city="Milano")
        self.authenticate_consumer(actions=("read",))

        response = self.client.get("/api/v1/events/?ordering=city")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        uuids = [item["uuid"] for item in response.data["results"][:2]]
        self.assertEqual(uuids, ["order-002", "order-001"])

    def test_create_event(self):
        self.authenticate_consumer(actions=("read", "create"))

        response = self.client.post(
            "/api/v1/events/",
            data=event_minimal_payload(uuid="crud-create-001", source="test_source", title="Nuovo evento CRUD"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        event = Event.objects.get(uuid="crud-create-001")
        self.assertEqual(event.created_by, "enterprise-consumer")

    def test_retrieve_event(self):
        event = self.create_event(uuid="retrieve-001")
        self.authenticate_consumer(actions=("read",))

        response = self.client.get(f"/api/v1/events/{event.pk}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["uuid"], "retrieve-001")

    def test_soft_delete_event(self):
        event = self.create_event(uuid="crud-delete-001")
        self.authenticate_consumer(actions=("read", "delete"))

        response = self.client.delete(f"/api/v1/events/{event.pk}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        event.refresh_from_db()
        self.assertFalse(event.is_active)
        self.assertEqual(event.deleted_by, "enterprise-consumer")

    def test_update_event_sets_updated_by(self):
        event = self.create_event(uuid="crud-update-001", title="Titolo iniziale")
        self.authenticate_consumer(actions=("read", "update"))

        payload = event_scraping_payload(
            uuid="crud-update-001",
            source=event.source,
            title="Titolo aggiornato",
        )

        response = self.client.patch(
            f"/api/v1/events/{event.pk}/",
            data=payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event.refresh_from_db()
        self.assertEqual(event.title, "Titolo aggiornato")
        self.assertEqual(event.updated_by, "enterprise-consumer")

    def test_clear_source_deletes_matching_events_only(self):
        self.create_event(uuid="clear-001", source="source-to-clear")
        self.create_event(uuid="clear-002", source="source-to-clear")
        self.create_event(uuid="keep-001", source="source-to-keep")
        self.authenticate_consumer(actions=("read", "delete"))

        response = self.client.delete("/api/v1/events/clear_source/?source=source-to-clear")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["deleted"], 2)
        self.assertEqual(response.data["source"], "source-to-clear")
        self.assertFalse(Event.objects.filter(source="source-to-clear").exists())
        self.assertTrue(Event.objects.filter(uuid="keep-001").exists())

    def test_clear_source_requires_source_parameter(self):
        self.authenticate_consumer(actions=("read", "delete"))

        response = self.client.delete("/api/v1/events/clear_source/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "source parameter is required")

    def test_free_plan_receives_reduced_fields(self):
        event = self.create_event(uuid="plan-free-001")
        self.authenticate_consumer(plan="free", actions=("read",))

        response = self.client.get(f"/api/v1/events/{event.pk}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(sorted(response.data.keys()), sorted(["id", "uuid", "title", "city", "date_start", "date_end", "category", "source"]))

    def test_get_caller_username_uses_authenticated_user_when_auth_payload_missing(self):
        request = APIRequestFactory().get("/api/v1/events/")
        user = create_staff_user(username="direct-caller")
        request.user = user

        view = ExternalEventViewSet()
        view.request = request

        self.assertEqual(view._get_caller_username(), user.username)

    def test_get_caller_username_returns_empty_for_anonymous_request(self):
        request = APIRequestFactory().get("/api/v1/events/")
        request.user = AnonymousUser()

        view = ExternalEventViewSet()
        view.request = request

        self.assertEqual(view._get_caller_username(), "")
