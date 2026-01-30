from rest_framework import serializers
from .models import ProductionEvent, StagingEvent, EtlRun, EtlError


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
    class Meta:
        model = StagingEvent
        fields = '__all__'


class StagingEventCreateSerializer(serializers.ModelSerializer):
    """Serializer per creare staging events via API esterna"""
    class Meta:
        model = StagingEvent
        fields = [
            'uuid', 'content_hash', 'source', 'url', 'title', 'description',
            'category', 'image_url', 'city', 'location_name', 'location_address',
            'price', 'website', 'date_start', 'date_end', 'time_start', 'time_end',
            'time_info', 'schedule', 'weekdays', 'raw_data', 'scraped_at'
        ]
        extra_kwargs = {
            'uuid': {'required': True},
            'source': {'required': True},
            'title': {'required': True},
        }


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
