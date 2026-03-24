from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from events.models import Event
from events.tasks import recompute_rank_scores
from events.tests.factories import create_event


class RecomputeRankScoresTaskTest(TestCase):
    def test_deactivates_expired_events_and_updates_active_scores(self):
        """Verifica l'automatica disattivazione degli eventi giunti alla scadenza, unita all'aggiornamento dei punteggi attivi restanti."""
        now = timezone.now()
        expired_event = create_event(
            uuid="expired-001",
            title="Evento scaduto",
            date_start=now - timedelta(days=3),
            date_end=now - timedelta(days=1),
            rank_score=99.0,
        )
        active_event = create_event(
            uuid="active-001",
            title="Evento attivo",
            description="Descrizione completa",
            image_url="https://example.com/image.jpg",
            price="10 EUR",
            location_address="Via Roma 1",
            url="https://example.com/event",
            category=["musica"],
            rank_score=0.0,
        )

        result = recompute_rank_scores()

        expired_event.refresh_from_db()
        active_event.refresh_from_db()

        self.assertFalse(expired_event.is_active)
        self.assertEqual(expired_event.deleted_by, "system")
        self.assertIsNotNone(expired_event.deleted_at)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["updated"], 1)
        self.assertGreater(active_event.rank_score, 0)

    def test_returns_zero_updates_when_scores_are_already_current(self):
        """Verifica che il task non esegua scritture inutimente se i rank score risultano già aggiornati."""
        event = create_event(uuid="stable-001", title="Evento stabile")
        event.rank_score = event.compute_rank_score()
        event.save(update_fields=["rank_score"])

        result = recompute_rank_scores()

        event.refresh_from_db()
        self.assertEqual(result, {"total": 1, "updated": 0})
        self.assertTrue(event.is_active)
