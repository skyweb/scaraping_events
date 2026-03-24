import hashlib
from datetime import datetime

from django.contrib.gis.geos import Point
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_serializer, extend_schema_field, OpenApiExample
from rest_framework import serializers

from .models import Event
from etl.models import EtlRun, EtlError


# Campi response filtrati per piano API
PLAN_FIELDS: dict[str, list[str]] = {
    "free": [
        "id", "uuid", "title", "city", "date_start", "date_end",
        "category", "source",
    ],
    # Enterprise e Flat: tutti i campi → non presenti in dict → EventSerializer
}


def get_plan_serializer_class(plan: str) -> type[serializers.ModelSerializer]:
    """Genera dinamicamente un ModelSerializer con i campi filtrati per piano."""
    fields = PLAN_FIELDS.get(plan)
    if fields is None:
        # Enterprise/Flat: tutti i campi
        return EventSerializer

    # Costruisce un serializer con location_coordinates come SerializerMethodField
    attrs: dict[str, object] = {}
    if "location_coordinates" in fields:
        attrs["location_coordinates"] = serializers.SerializerMethodField()
        attrs["get_location_coordinates"] = EventSerializer.get_location_coordinates

    meta_attrs = {"model": Event, "fields": list(fields)}
    attrs["Meta"] = type("Meta", (), meta_attrs)

    return type(f"Event{plan.capitalize()}PlanSerializer", (serializers.ModelSerializer,), attrs)


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Evento produzione",
            value={
                "id": 1,
                "uuid": "a1b2c3d4e5f6g7h8",
                "title": "Concerto Jazz al Blue Note",
                "city": "Milano",
                "source": "city_today",
                "url": "https://www.milanotoday.it/eventi/concerto-jazz.html",
                "description": "Serata jazz con artisti internazionali",
                "category": ["Musica", "Concerti"],
                "image_url": "https://example.com/jazz.jpg",
                "location_name": "Blue Note Milano",
                "location_address": "Via Borsieri 37, Milano",
                "price": "25.00",
                "date_start": "2026-04-15",
                "date_end": "2026-04-15",
                "is_active": True,
                "created_at": "2026-03-20T10:00:00Z",
                "updated_at": "2026-03-20T10:00:00Z",
            },
            response_only=True,
        ),
    ]
)
class EventSerializer(serializers.ModelSerializer):
    """Serializer completo per gli eventi (tutti i campi)."""
    location_coordinates = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = '__all__'

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_location_coordinates(self, obj) -> dict[str, float] | None:
        """Converte il PointField GeoDjango in dizionario {lat, lng}."""
        if obj.location_coordinates:
            return {'lat': obj.location_coordinates.y, 'lng': obj.location_coordinates.x}
        return None


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Lista eventi",
            value={
                "id": 1,
                "uuid": "a1b2c3d4e5f6g7h8",
                "title": "Concerto Jazz al Blue Note",
                "city": "Milano",
                "source": "city_today",
                "date_start": "2026-04-15",
                "date_end": "2026-04-15",
                "is_active": True,
                "category": ["Musica", "Concerti"],
            },
            response_only=True,
        ),
    ]
)
class EventListSerializer(serializers.ModelSerializer):
    """Serializer leggero per liste"""
    class Meta:
        model = Event
        fields = [
            'id', 'uuid', 'title', 'city', 'source',
            'date_start', 'date_end', 'is_active', 'category'
        ]


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Staging event",
            value={
                "id": 42,
                "uuid": "b2c3d4e5f6a7b8c9",
                "content_hash": "f1e2d3c4b5a6f7e8",
                "source": "puglia_culture",
                "title": "Festival della Taranta",
                "city": "Lecce",
                "location_name": "Piazza Duomo",
                "location_address": "Piazza del Duomo, Lecce",
                "location_coordinates": {"lat": 40.3516, "lng": 18.1718},
                "date_start": "2026-08-20T21:00:00Z",
                "date_end": "2026-08-20T23:59:00Z",
                "url": "https://pugliaculture.it/eventi/taranta",
                "description": "La notte della Taranta edizione 2026",
                "image_url": "https://example.com/taranta.jpg",
                "price": "Gratuito",
                "category": ["Musica", "Festival"],
                "scraped_at": "2026-03-20T10:30:00Z",
                "loaded_at": "2026-03-20T10:31:00Z",
                "created_at": "2026-03-20T10:31:00Z",
            },
            response_only=True,
        ),
    ]
)
class EventBulkResponseSerializer(serializers.ModelSerializer):
    """Serializer compatto per la risposta bulk (solo campi essenziali)."""

    class Meta:
        model = Event
        fields = ['id', 'uuid', 'content_hash', 'source', 'title', 'created_at']


def _parse_point(coords: dict) -> Point | None:
    """Converte {lat, lng} in Point GeoDjango. Restituisce None se le coordinate non sono valide o sono (0, 0)."""
    try:
        lat = float(coords.get('lat') or 0)
        lng = float(coords.get('lng') or 0)
        if lat and lng:
            return Point(lng, lat, srid=4326)  # Point(x=lng, y=lat)
    except (ValueError, TypeError):
        pass
    return None


class CityNestedSerializer(serializers.Serializer):
    """Dati città annidati nel formato scraping."""
    city_name = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    location_name = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    location_address = serializers.CharField(max_length=500, required=False, allow_blank=True, allow_null=True)
    location_coords = serializers.DictField(required=False, allow_null=True)


class DatesNestedSerializer(serializers.Serializer):
    """Dati date annidati nel formato scraping."""
    date_start = serializers.CharField(max_length=30, required=False, allow_blank=True, allow_null=True)
    date_end = serializers.CharField(max_length=30, required=False, allow_blank=True, allow_null=True)


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Formato scraping (flat)",
            value={
                "uuid": "b2c3d4e5f6a7b8c9",
                "content_hash": "f1e2d3c4b5a6f7e8",
                "source": "puglia_culture",
                "title": "Festival della Taranta",
                "stars": 4,
                "category": ["Musica", "Festival"],
                "city": {
                    "city": "Lecce",
                    "location_name": "Piazza Duomo",
                    "location_address": "Piazza del Duomo, Lecce",
                    "location_coordinates": {"lat": "40.3516", "lng": "18.1718"}
                },
                "dates": {
                    "date_start": "2026-08-20",
                    "date_end": "2026-08-20",
                },
                "url": "https://pugliaculture.it/eventi/taranta",
                "description": "La notte della Taranta edizione 2026",
                "image_url": "https://example.com/taranta.jpg",
                "price": "Gratuito",
                "scraped_at": "2026-03-20 10:30:00"
            },
            request_only=True,
        ),
    ]
)
class EventScrapingSerializer(serializers.Serializer):
    """
    Formato event scraping — struttura definita in templates.json.

    Struttura attesa:
        {
          "uuid": "...",
          "content_hash": "...",
          "source": "puglia_culture",
          "title": "...",
          "stars": 3,
          "category": ["teatro", "..."],
          "section": { "teatro": { "rassegna": "...", "cast": "..." } },
          "city": {
            "city_id": null,
            "city_name": "...",
            "location_name": "...",
            "location_address": "...",
            "location_coordinates": { "lat": "...", "lng": "..." }
          },
          "dates": {
            "date_start": "YYYY-MM-DD",
            "date_end": "YYYY-MM-DD",
          },
          "url": "...",
          "description": "...",
          "image_url": "...",
          "price": "...",
          "scraped_at": "YYYY-MM-DD HH:MM:SS"
        }
    """
    uuid = serializers.CharField(max_length=64)
    content_hash = serializers.CharField(max_length=64, required=False, allow_null=True, allow_blank=True)
    source = serializers.CharField(max_length=50)
    title = serializers.CharField(max_length=1000)
    stars = serializers.IntegerField(required=False, allow_null=True)
    category = serializers.ListField(child=serializers.CharField(), required=False, allow_null=True)
    city = CityNestedSerializer(required=False, allow_null=True)
    dates = DatesNestedSerializer(required=False, allow_null=True)
    url = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    description = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    image_url = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    price = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    scraped_at = serializers.DateTimeField(required=False, allow_null=True)
    raw_data = serializers.JSONField(required=False, allow_null=True)

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        """Parsa date in formato flessibile: YYYY-MM-DD, YYYY-MM-DD HH:MM, ISO 8601."""
        if not value or not value.strip():
            return None
        value = value.strip()
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
            try:
                parsed = datetime.strptime(value, fmt)
                if timezone.is_naive(parsed):
                    return timezone.make_aware(parsed, timezone.get_current_timezone())
                return parsed
            except ValueError:
                continue
        return None

    @staticmethod
    def _flatten_spider_format(nested: dict) -> dict:
        """
        Converte il formato nested degli spider (uuid, title, meta, data)
        nel formato flat atteso dal serializer.
        """
        meta = nested.get("meta") or {}
        event_data = nested.get("data") or {}
        section = event_data.get("section") or {}

        flat = {
            "uuid": nested.get("uuid"),
            "title": nested.get("title"),
            "content_hash": meta.get("content_hash"),
            "source": meta.get("source"),
            "url": meta.get("url"),
            "scraped_at": meta.get("scraped_at"),
            "description": event_data.get("description"),
            "category": event_data.get("category"),
            "image_url": event_data.get("image_url"),
            "city": event_data.get("city"),
            "dates": event_data.get("dates"),
            "price": section.get("price"),
            # raw_data = intero blocco "data" originale dello spider
            "raw_data": event_data,
        }

        return flat

    def to_internal_value(self, data):
        """Converte il formato nested dello spider in flat e normalizza campi (coordinate, date, batch_file)."""
        # Salva il JSON originale del POST prima di qualsiasi trasformazione
        raw_data = dict(data) if isinstance(data, dict) else data

        # Estrai batch_file: prima da meta (nuovo formato), poi da _batch_file (legacy)
        batch_file = (data.get('meta') or {}).get('batch_file') or data.pop('_batch_file', None)

        # Supporto formato nested spider (uuid, title, meta, data)
        # Trasforma in formato flat atteso dal serializer
        if "meta" in data and "data" in data:
            data = self._flatten_spider_format(data)

        validated = super().to_internal_value(data)
        validated['_batch_file'] = batch_file

        city = validated.get('city') or {}
        dates = validated.get('dates') or {}

        location_coordinates = _parse_point(city.get('location_coords') or {})

        normalized = {
            'content_hash': validated.get('content_hash') or None,
            'url': validated.get('url') or None,
            'description': validated.get('description') or None,
            'image_url': validated.get('image_url') or None,
            'price': validated.get('price') or None,
            'scraped_at': validated.get('scraped_at'),
            'category': [c for c in (validated.get('category') or []) if c] or None,
            'city': city.get('city_name') or None,
            'location_name': city.get('location_name') or None,
            'location_address': city.get('location_address') or None,
            'location_coordinates': location_coordinates,
            'date_start': self._parse_datetime(dates.get('date_start')),
            'date_end': self._parse_datetime(dates.get('date_end')),
            'raw_data': raw_data,
            'batch_file': validated.get('_batch_file'),
        }

        if 'uuid' in validated:
            normalized['uuid'] = validated['uuid']
        if 'source' in validated:
            normalized['source'] = validated['source']
        if 'title' in validated:
            normalized['title'] = validated['title']

        return normalized

    def create(self, validated_data):
        """Upsert su uuid."""
        validated_data.pop('_batch_file', None)
        uuid = validated_data.pop('uuid')
        Event.objects.update_or_create(uuid=uuid, defaults=validated_data)
        return Event.objects.get(uuid=uuid)

    def update(self, instance, validated_data):
        """Aggiorna l'istanza esistente supportando PATCH/PUT."""
        validated_data.pop('_batch_file', None)
        validated_data.pop('uuid', None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance


class EventLegacySerializer(serializers.Serializer):
    """
    Formato legacy — struttura nested con 'details' e 'list'.
    Mantenuto per backward compatibility con spider precedenti.

    Struttura attesa:
        {
          "title": "...",
          "source_url": "...",
          "source": "...",
          "list": { "image": "", "category": [], "location_name": "", "typology": "" },
          "details": {
            "where": { "name": "", "location_address": "", "location_coords": {"lat": "", "lng": ""} },
            "image": "",
            "price": "",
            "when": { "date_start": "", "date_end": "", "raw_text": "" },
            "description": "",
            "informations": { "raw_text": "" }
          },
          "scraped_at": "",
          "raw_data": null
        }
    """
    title = serializers.CharField()
    source = serializers.CharField()
    source_url = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    scraped_at = serializers.DateTimeField(required=False, allow_null=True)
    raw_data = serializers.JSONField(required=False, allow_null=True)
    list = serializers.DictField(required=False, default=dict)
    details = serializers.DictField(required=False, default=dict)

    def to_internal_value(self, data):
        """Converte il formato legacy nested (details, list) in flat e genera uuid/content_hash."""
        validated = super().to_internal_value(data)

        list_data = validated.get('list') or {}
        details = validated.get('details') or {}
        where = details.get('where') or {}
        when = details.get('when') or {}
        informations = details.get('informations') or {}

        location_name = (
            where.get('name')
            or where.get('location_name')
            or list_data.get('location_name')
        ) or None

        location_coordinates = _parse_point(where.get('location_coords') or {})

        image_url = details.get('image') or list_data.get('image') or None

        category = list_data.get('category') or []
        if isinstance(category, str):
            category = [c.strip() for c in category.split(',') if c.strip()]
        category = [c for c in category if c] or None

        flat = {
            'title': validated['title'],
            'source': validated['source'],
            'url': validated.get('source_url') or None,
            'scraped_at': validated.get('scraped_at'),
            'raw_data': validated.get('raw_data'),
            'description': details.get('description') or None,
            'price': details.get('price') or None,
            'image_url': image_url,
            'category': category,
            'location_name': location_name,
            'location_address': where.get('location_address') or None,
            'location_coordinates': location_coordinates,
            'date_start': EventScrapingSerializer._parse_datetime(when.get('date_start')),
            'date_end': EventScrapingSerializer._parse_datetime(when.get('date_end')),
        }

        # Genera uuid: title + date_start + location_name
        uuid_input = "".join([str(flat.get(k) or '') for k in ('title', 'date_start', 'location_name')])
        flat['uuid'] = hashlib.sha256(uuid_input.encode()).hexdigest()[:32]

        # Genera content_hash: description + price
        hash_input = "".join([str(flat.get(k) or '') for k in ('description', 'price')])
        flat['content_hash'] = hashlib.sha256(hash_input.encode()).hexdigest()[:32]

        return flat

    def create(self, validated_data):
        """Upsert su uuid."""
        uuid = validated_data.pop('uuid')
        Event.objects.update_or_create(uuid=uuid, defaults=validated_data)
        return Event.objects.get(uuid=uuid)


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "ETL run completata",
            value={
                "id": 1,
                "run_type": "etl_events_daily",
                "staging_count": 350,
                "inserted_count": 280,
                "updated_count": 70,
                "status": "completed",
                "started_at": "2026-03-20T06:00:00Z",
                "staging_completed_at": "2026-03-20T06:15:00Z",
                "upsert_completed_at": "2026-03-20T06:20:00Z",
                "duration_seconds": 1200.0,
            },
            response_only=True,
        ),
    ]
)
class EtlRunSerializer(serializers.ModelSerializer):
    """Serializer per le esecuzioni ETL con durata calcolata in secondi."""
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = EtlRun
        fields = '__all__'

    @extend_schema_field(OpenApiTypes.FLOAT)
    def get_duration_seconds(self, obj) -> float | None:
        """Calcola la durata totale dell'ETL in secondi (da started_at a upsert_completed_at)."""
        if obj.upsert_completed_at and obj.started_at:
            return (obj.upsert_completed_at - obj.started_at).total_seconds()
        return None


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Errore ETL",
            value={
                "id": 1,
                "etl_run": 1,
                "event_uuid": "a1b2c3d4e5f6g7h8",
                "error_type": "ValidationError",
                "error_message": "Campo 'title' obbligatorio mancante",
                "raw_data": {"source": "city_today", "url": "https://..."},
                "created_at": "2026-03-20T06:15:30Z",
            },
            response_only=True,
        ),
    ]
)
class EtlErrorSerializer(serializers.ModelSerializer):
    """Serializer per gli errori ETL con tipo, sorgente e messaggio."""
    class Meta:
        model = EtlError
        fields = '__all__'


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Dashboard statistiche",
            value={
                "total_events": 12450,
                "active_events": 8320,
                "events_by_city": {"Milano": 2100, "Roma": 1850, "Torino": 980, "Bologna": 750},
                "events_by_source": {"city_today": 6500, "artribune": 1200, "zero_eu": 800},
                "recent_etl_runs": [
                    {"id": 10, "run_type": "etl_events_daily", "status": "completed",
                     "staging_count": 350, "started_at": "2026-03-20T06:00:00Z", "duration_seconds": 1200.0}
                ],
                "staging_count": 420,
            },
            response_only=True,
        ),
    ]
)
class DashboardStatsSerializer(serializers.Serializer):
    """Statistiche per la dashboard"""
    total_events = serializers.IntegerField()
    active_events = serializers.IntegerField()
    events_by_city = serializers.DictField()
    events_by_source = serializers.DictField()
    recent_etl_runs = EtlRunSerializer(many=True)
    staging_count = serializers.IntegerField()


class FailedEventSerializer(serializers.Serializer):
    """Serializer per un evento fallito nella risposta bulk (dati originali, errori e indice)."""
    original_data = serializers.JSONField(help_text="The original event data that failed to save.")
    errors = serializers.JSONField(help_text="Detailed validation errors for the event.")
    index = serializers.IntegerField(help_text="Index of the event in the original request list.")


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Bulk response (successo parziale)",
            value={
                "created_count": 48,
                "failed_count": 2,
                "successful_events": [
                    {"id": 42, "uuid": "b2c3d4e5f6a7b8c9", "source": "puglia_culture",
                     "title": "Festival della Taranta", "created_at": "2026-03-20T10:31:00Z"}
                ],
                "failed_events": [
                    {"index": 5, "original_data": {"source": "city_today"},
                     "errors": {"title": ["Questo campo e' obbligatorio."]}}
                ],
            },
            response_only=True,
        ),
    ]
)
class BulkProcessResponseSerializer(serializers.Serializer):
    """Serializer per la risposta bulk: eventi creati, falliti e conteggi."""
    successful_events = EventSerializer(many=True, help_text="List of events that were successfully created/updated.")
    failed_events = FailedEventSerializer(many=True, help_text="List of events that failed to save, with their errors.")
    created_count = serializers.IntegerField(help_text="Number of events successfully created.")
    failed_count = serializers.IntegerField(help_text="Number of events that failed to save.")


# =============================================================================
# Serializer per risposte Swagger (spostati da views.py)
# =============================================================================

class BulkCreateResponseSerializer(serializers.Serializer):
    """Serializer di risposta per il bulk create (conteggio e lista eventi creati)."""
    created = serializers.IntegerField()
    events = EventSerializer(many=True)


class BulkCreateRequestSerializer(serializers.Serializer):
    """Serializer di richiesta per il bulk create (lista di eventi)."""
    events = EventScrapingSerializer(many=True)


class ClearSourceResponseSerializer(serializers.Serializer):
    """Serializer di risposta per la cancellazione per sorgente (conteggio e nome sorgente)."""
    deleted = serializers.IntegerField()
    source = serializers.CharField()


class BulkAcceptedResponseSerializer(serializers.Serializer):
    """Serializer di risposta per il bulk async accettato (task_id, stato e messaggio)."""
    task_id = serializers.CharField()
    status = serializers.CharField()
    message = serializers.CharField()


class BulkTaskStatusResponseSerializer(serializers.Serializer):
    """Serializer di risposta per lo stato di un task bulk asincrono."""
    task_id = serializers.CharField()
    status = serializers.CharField()
    result = serializers.JSONField(required=False, allow_null=True)


class ErrorResponseSerializer(serializers.Serializer):
    """Serializer generico per le risposte di errore con campo 'error'."""
    error = serializers.CharField()


class CityCountSerializer(serializers.Serializer):
    """Serializer per il conteggio eventi per città."""
    city = serializers.CharField()
    count = serializers.IntegerField()


class SourceCountSerializer(serializers.Serializer):
    """Serializer per il conteggio eventi per sorgente."""
    source = serializers.CharField()
    count = serializers.IntegerField()


class ToggleActiveResponseSerializer(serializers.Serializer):
    """Serializer di risposta per il toggle attivo/inattivo di un evento."""
    is_active = serializers.BooleanField()


# Alias per retrocompatibilità temporanea
StagingEventSerializer = EventSerializer
StagingEventBulkResponseSerializer = EventBulkResponseSerializer
StagingEventScrapingSerializer = EventScrapingSerializer
StagingEventLegacySerializer = EventLegacySerializer
ProductionEventSerializer = EventSerializer
ProductionEventListSerializer = EventListSerializer
