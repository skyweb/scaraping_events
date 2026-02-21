import hashlib

from django.contrib.gis.geos import Point
from rest_framework import serializers

from .models import ProductionEvent, StagingEvent
from etl.models import EtlRun, EtlError


class ProductionEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductionEvent
        fields = '__all__'


class ProductionEventListSerializer(serializers.ModelSerializer):
    """Serializer leggero per liste"""
    class Meta:
        model = ProductionEvent
        fields = [
            'id', 'uuid', 'title', 'city', 'source',
            'date_start', 'date_end', 'is_active', 'category'
        ]


class StagingEventSerializer(serializers.ModelSerializer):
    # PointField non è supportato nativamente da DRF — rappresentato come {lat, lng}
    location_coordinates = serializers.SerializerMethodField()

    class Meta:
        model = StagingEvent
        fields = '__all__'

    def get_location_coordinates(self, obj):
        if obj.location_coordinates:
            return {'lat': obj.location_coordinates.y, 'lng': obj.location_coordinates.x}
        return None


def _parse_point(coords: dict) -> Point | None:
    """Converte {lat, lng} in Point GeoDjango. Restituisce None se le coordinate non sono valide."""
    try:
        lat = float(coords.get('lat') or 0)
        lng = float(coords.get('lng') or 0)
        if lat and lng:
            return Point(lng, lat, srid=4326)  # Point(x=lng, y=lat)
    except (ValueError, TypeError):
        pass
    return None


class StagingEventScrapingSerializer(serializers.Serializer):
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
            "time_start": "HH:MM",
            "date_end": "YYYY-MM-DD",
            "time_end": "HH:MM",
            "time_info": "..."
          },
          "url": "...",
          "description": "...",
          "image_url": "...",
          "price": "...",
          "info_extra": { "info_e_costi": "...", "info_e_contatti": "..." },
          "scraped_at": "YYYY-MM-DD HH:MM:SS"
        }
    """
    uuid = serializers.CharField()
    content_hash = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    source = serializers.CharField()
    title = serializers.CharField()
    stars = serializers.IntegerField(required=False, allow_null=True)
    category = serializers.ListField(child=serializers.CharField(), required=False, allow_null=True)
    section = serializers.DictField(required=False, allow_null=True)
    city = serializers.DictField(required=False, allow_null=True)
    dates = serializers.DictField(required=False, allow_null=True)
    url = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    description = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    image_url = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    price = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    info_extra = serializers.DictField(required=False, allow_null=True)
    scraped_at = serializers.DateTimeField(required=False, allow_null=True)
    raw_data = serializers.JSONField(required=False, allow_null=True)

    def to_internal_value(self, data):
        # Salva il JSON originale del POST prima di qualsiasi trasformazione
        raw_data = dict(data) if isinstance(data, dict) else data

        validated = super().to_internal_value(data)

        city = validated.get('city') or {}
        dates = validated.get('dates') or {}
        section_raw = validated.get('section') or {}
        stars = validated.get('stars')
        info_extra = dict(validated.get('info_extra') or {})

        # Sezione: prima chiave come stringa, dict completo in info_extra
        section_str = next(iter(section_raw), None)
        if section_raw:
            info_extra['section'] = section_raw
        if stars is not None:
            info_extra['stars'] = stars

        # Coordinate
        location_coordinates = _parse_point(city.get('location_coordinates') or {})

        return {
            'uuid': validated['uuid'],
            'content_hash': validated.get('content_hash') or None,
            'source': validated['source'],
            'title': validated['title'],
            'url': validated.get('url') or None,
            'description': validated.get('description') or None,
            'image_url': validated.get('image_url') or None,
            'price': validated.get('price') or None,
            'scraped_at': validated.get('scraped_at'),
            'raw_data': validated.get('raw_data'),
            'category': [c for c in (validated.get('category') or []) if c] or None,
            'section': section_str,
            'city_name': city.get('city_name') or None,
            'location_name': city.get('location_name') or None,
            'location_address': city.get('location_address') or None,
            'location_coordinates': location_coordinates,
            'date_start': dates.get('date_start') or None,
            'date_end': dates.get('date_end') or None,
            'time_start': dates.get('time_start') or None,
            'time_end': dates.get('time_end') or None,
            'time_info': dates.get('time_info') or None,
            'info_extra': info_extra or None,
            'raw_data': raw_data,
        }

    def create(self, validated_data):
        """Upsert su uuid."""
        uuid = validated_data.pop('uuid')
        StagingEvent.objects.update_or_create(uuid=uuid, defaults=validated_data)
        return StagingEvent.objects.get(uuid=uuid)


class StagingEventLegacySerializer(serializers.Serializer):
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
            "informations": { "website": "", "raw_text": "" }
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

        info_extra = {}
        if informations:
            info_extra.update(informations)
        if where.get('raw_text'):
            info_extra['where_raw'] = where['raw_text']

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
            'section': list_data.get('typology') or None,
            'location_name': location_name,
            'location_address': where.get('location_address') or None,
            'location_coordinates': location_coordinates,
            'date_start': when.get('date_start') or None,
            'date_end': when.get('date_end') or None,
            'time_info': when.get('raw_text') or None,
            'info_extra': info_extra or None,
        }

        # Genera uuid: title + date_start + location_name
        uuid_input = "".join([str(flat.get(k) or '') for k in ('title', 'date_start', 'location_name')])
        flat['uuid'] = hashlib.sha256(uuid_input.encode()).hexdigest()[:16]

        # Genera content_hash: description + price
        hash_input = "".join([str(flat.get(k) or '') for k in ('description', 'price')])
        flat['content_hash'] = hashlib.sha256(hash_input.encode()).hexdigest()[:16]

        return flat

    def create(self, validated_data):
        """Upsert su uuid."""
        uuid = validated_data.pop('uuid')
        StagingEvent.objects.update_or_create(uuid=uuid, defaults=validated_data)
        return StagingEvent.objects.get(uuid=uuid)


class EtlRunSerializer(serializers.ModelSerializer):
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = EtlRun
        fields = '__all__'

    def get_duration_seconds(self, obj):
        if obj.upsert_completed_at and obj.started_at:
            return (obj.upsert_completed_at - obj.started_at).total_seconds()
        return None


class EtlErrorSerializer(serializers.ModelSerializer):
    class Meta:
        model = EtlError
        fields = '__all__'


class DashboardStatsSerializer(serializers.Serializer):
    """Statistiche per la dashboard"""
    total_events = serializers.IntegerField()
    active_events = serializers.IntegerField()
    events_by_city = serializers.DictField()
    events_by_source = serializers.DictField()
    recent_etl_runs = EtlRunSerializer(many=True)
    staging_count = serializers.IntegerField()


class FailedEventSerializer(serializers.Serializer):
    original_data = serializers.JSONField(help_text="The original event data that failed to save.")
    errors = serializers.JSONField(help_text="Detailed validation errors for the event.")
    index = serializers.IntegerField(help_text="Index of the event in the original request list.")


class BulkProcessResponseSerializer(serializers.Serializer):
    successful_events = StagingEventSerializer(many=True, help_text="List of events that were successfully created/updated.")
    failed_events = FailedEventSerializer(many=True, help_text="List of events that failed to save, with their errors.")
    created_count = serializers.IntegerField(help_text="Number of events successfully created.")
    failed_count = serializers.IntegerField(help_text="Number of events that failed to save.")
