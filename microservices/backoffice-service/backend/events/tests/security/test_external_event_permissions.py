from datetime import timedelta

from django.utils import timezone
from rest_framework import status

from events.tests.helpers import ExternalAPITestCase, event_minimal_payload


class ExternalEventSecurityTest(ExternalAPITestCase):
    def test_request_without_auth_is_rejected(self):
        self.clear_auth()

        response = self.client.get("/api/v1/events/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_read_only_consumer_cannot_create(self):
        self.authenticate_consumer(actions=("read",))

        response = self.client.post(
            "/api/v1/events/",
            data=event_minimal_payload(uuid="sec-create-001"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_expired_consumer_is_blocked(self):
        api_consumer = self.authenticate_consumer(actions=("read",))
        api_consumer.expires_at = timezone.now() - timedelta(minutes=1)
        api_consumer.save(update_fields=["expires_at"])

        response = self.client.get("/api/v1/events/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_free_plan_does_not_expose_internal_fields(self):
        event = self.create_event(uuid="free-plan-001", raw_data={"internal": True}, created_by="system")
        self.authenticate_consumer(plan="free", actions=("read",))

        response = self.client.get(f"/api/v1/events/{event.pk}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("raw_data", response.data)
        self.assertNotIn("created_by", response.data)
