from __future__ import annotations

from django.test import TestCase
from rest_framework.test import APIClient

from events.models import Event
from events.tests.factories import create_api_consumer, create_event, create_staff_user


def event_scraping_payload(**overrides) -> dict:
    """Genera un payload tipico proveniente da una passata di scraping completa, per i test mock."""
    data = {
        "uuid": "bulk-test-001",
        "content_hash": "hash001",
        "source": "test_spider",
        "title": "Concerto Jazz",
        "category": ["musica", "jazz"],
        "city": {
            "city_name": "Milano",
            "location_name": "Blue Note",
            "location_address": "Via Borsieri 37",
            "location_coords": {"lat": "45.4942", "lng": "9.1970"},
        },
        "dates": {
            "date_start": "2026-06-15",
            "date_end": "2026-06-15",
        },
        "url": "https://example.com/concerto",
        "description": "Serata jazz dal vivo.",
        "image_url": "https://example.com/img.jpg",
        "price": "25 EUR",
        "scraped_at": "2026-06-01T10:00:00Z",
    }
    data.update(overrides)
    return data


def event_legacy_payload(**overrides) -> dict:
    """Genera un payload emulante il vecchio formato strutturale per i test di retrocompatibilità."""
    data = {
        "title": "Mostra Caravaggio",
        "source": "test_legacy",
        "source_url": "https://example.com/mostra",
        "scraped_at": "2026-06-01T10:00:00Z",
        "list": {
            "image": "https://example.com/caravaggio.jpg",
            "category": ["arte", "mostre"],
            "location_name": "Palazzo Reale",
        },
        "details": {
            "where": {
                "name": "Palazzo Reale",
                "location_address": "Piazza Duomo 12, Milano",
                "location_coords": {"lat": "45.4637", "lng": "9.1912"},
            },
            "image": "https://example.com/caravaggio-detail.jpg",
            "price": "15 EUR",
            "when": {
                "date_start": "2026-06-01",
                "date_end": "2026-08-31",
                "raw_text": "Da martedi a domenica, 10:00-19:00",
            },
            "description": "Esposizione delle opere di Caravaggio.",
            "informations": {
                "raw_text": "Info: 02-12345678",
            },
        },
    }
    data.update(overrides)
    return data


def puglia_culture_payload(**overrides) -> dict:
    """Genera un payload nel formato nested prodotto dallo spider puglia_culture."""
    data = {
        "uuid": "puglia-test-001",
        "title": "Spettacolo di Prova - Teatro Paisiello",
        "data": {
            "description": "Uno spettacolo teatrale di prova nel cuore del Salento.",
            "category": ["teatro", "spettacolo"],
            "image_url": "https://www.pugliaculture.it/img/spettacolo.jpg",
            "dates": {
                "date_start": "2026-04-15 21:00",
                "date_end": "2026-04-15 23:00",
                "date_display": "",
            },
            "city": {
                "city_name": "Lecce",
                "location_name": "Teatro Paisiello",
            },
            "section": {
                "casting": "<div>Regia: Mario Rossi</div>",
                "info_e_costi": "Biglietti: 15 EUR",
            },
        },
        "meta": {
            "content_hash": "deadbeef1234",
            "url": "https://www.pugliaculture.it/spettacolo/prova",
            "category": "spettacolo",
            "source": "puglia_culture",
            "scraped_at": "2026-04-01T10:00:00Z",
        },
    }
    data.update(overrides)
    return data


def event_minimal_payload(**overrides) -> dict:
    """Genera un payload stringato ed essenziale, con la dotazione minima per esser ritenuto ammissibile."""
    data = {
        "uuid": "bulk-min-001",
        "source": "test_spider",
        "title": "Evento Minimo",
    }
    data.update(overrides)
    return data


class ExternalAPITestCase(TestCase):
    client_class = APIClient

    def setUp(self):
        self.client = APIClient()

    def authenticate_consumer(
        self,
        *,
        username: str = "enterprise-consumer",
        plan: str = "enterprise",
        actions: tuple[str, ...] = ("read", "create", "update", "delete"),
    ):
        """Autentica un consumatore in ambito test aggiungendovi header dedicati."""
        consumer = create_api_consumer(username=username, plan=plan, actions=actions)
        self.client.credentials(
            HTTP_X_CONSUMER_PLAN=plan,
            HTTP_X_CONSUMER_USERNAME=username,
        )
        return consumer

    def clear_auth(self):
        """Azzera brutalmente i parametri di autenticazione dell'API client."""
        self.client.credentials()

    def create_event(self, **overrides):
        """Instanzia un evento passando alla factory gli overwrite richiesti in maniera opzionale."""
        return create_event(**overrides)


class InternalAPITestCase(TestCase):
    client_class = APIClient

    def setUp(self):
        self.client = APIClient()
        self.user = create_staff_user()
        self.client.force_login(self.user)

    def create_event(self, **overrides):
        """Genera per vie traverse (factory) un nuovo evento configurabile ad hoc per questo tipo di test."""
        return create_event(**overrides)

    def create_staging_event(self, **overrides):
        """Crea un evento forzando lo status in stato embrionale o d'attesa (Staging)."""
        return create_event(status=Event.Status.STAGING, **overrides)
