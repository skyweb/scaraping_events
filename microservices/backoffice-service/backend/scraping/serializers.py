from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer, OpenApiExample

from .models import ScrapingWebsite, ScrapingCategory, ScrapingLocation


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Website scraping",
            value={
                "id": 1, "name": "MilanoToday",
                "source_url": "https://www.milanotoday.it",
                "spider_name": "city_today",
                "cms": "custom",
                "cms_display": "Custom",
                "is_active": True, "notes": "50+ citta italiane"
            },
            response_only=True,
        ),
    ]
)
class ScrapingWebsiteSerializer(serializers.ModelSerializer):
    """Serializer per i portali web scrapati con label CMS leggibile."""
    cms_display = serializers.CharField(source='get_cms_display', read_only=True)

    class Meta:
        model = ScrapingWebsite
        fields = [
            'id', 'name', 'source_url', 'spider_name',
            'cms', 'cms_display', 'is_active', 'notes',
        ]


class ScrapingCategorySerializer(serializers.ModelSerializer):
    """Serializer per le categorie aggregate (nome e conteggio eventi)."""
    class Meta:
        model = ScrapingCategory
        fields = ['categoria', 'count']


class ScrapingLocationSerializer(serializers.ModelSerializer):
    """Serializer per le location aggregate (nome, città e conteggio eventi)."""
    class Meta:
        model = ScrapingLocation
        fields = ['location_name', 'city_name', 'count']
