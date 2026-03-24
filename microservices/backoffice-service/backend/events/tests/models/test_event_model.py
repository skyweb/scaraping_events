from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from events.models import Event
from events.tests.factories import create_event


class EventModelTest(TestCase):
    def test_string_representation_uses_status_title_and_city(self):
        event = create_event(title="Festival", city="Torino", status=Event.Status.PUBLISHED)
        self.assertEqual(str(event), "[Pubblicato] Festival - Torino")

    def test_compute_rank_score_rewards_completeness_and_future_date(self):
        now = timezone.now()
        event = create_event(
            source="borghi_italia",
            description="Evento completo",
            image_url="https://example.com/image.jpg",
            price="10 EUR",
            category=["musica"],
            location_address="Via Roma 1",
            url="https://example.com/event",
            schema_org={"@type": "Event"},
            date_start=now + timedelta(days=3),
            date_end=now + timedelta(days=3, hours=2),
            scraped_at=now,
        )

        self.assertGreater(event.compute_rank_score(), 70)

    def test_compute_rank_score_returns_zero_for_past_event_without_extra_data(self):
        now = timezone.now()
        event = create_event(
            description=None,
            image_url=None,
            location_coordinates=None,
            price=None,
            category=None,
            location_address=None,
            url=None,
            source="generic_source",
            schema_org=None,
            date_start=now - timedelta(days=10),
            date_end=now - timedelta(days=9),
            scraped_at=now - timedelta(days=120),
        )

        self.assertEqual(event.compute_rank_score(), 5.0)
