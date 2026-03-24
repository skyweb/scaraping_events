from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.utils import timezone

from api_consumers.models import ApiConsumer
from events.models import Event

User = get_user_model()


def api_permissions(*actions: str) -> dict[str, list[str]]:
    """Crea una matrice permessi minimale per la risorsa events."""
    return {"events": list(actions)}


def create_api_consumer(
    username: str = "test-consumer",
    plan: str = "enterprise",
    actions: tuple[str, ...] = ("read", "create", "update", "delete"),
) -> ApiConsumer:
    return ApiConsumer.objects.create(
        username=username,
        plan=plan,
        auth_type="api_key",
        api_key=f"key-{username}",
        api_permissions=api_permissions(*actions),
    )


def create_staff_user(username: str = "staff") -> User:
    return User.objects.create_user(
        username=username,
        password="testpass123",
        is_staff=True,
    )


def create_event(**overrides) -> Event:
    now = timezone.now()
    defaults = {
        "uuid": "event-001",
        "source": "test_source",
        "title": "Evento di test",
        "status": Event.Status.PUBLISHED,
        "city": "Roma",
        "date_start": now + timedelta(days=10),
        "date_end": now + timedelta(days=10, hours=2),
        "scraped_at": now,
        "location_coordinates": Point(12.4964, 41.9028, srid=4326),
        "is_active": True,
    }
    defaults.update(overrides)
    return Event.objects.create(**defaults)
