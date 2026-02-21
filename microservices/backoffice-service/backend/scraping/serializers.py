from rest_framework import serializers

from .models import ScrapingWebsite, ScrapingCategory, ScrapingLocation


class ScrapingWebsiteSerializer(serializers.ModelSerializer):
    cms_display = serializers.CharField(source='get_cms_display', read_only=True)

    class Meta:
        model = ScrapingWebsite
        fields = [
            'id', 'name', 'source_url', 'spider_name',
            'cms', 'cms_display', 'is_active', 'notes',
        ]


class ScrapingCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ScrapingCategory
        fields = ['categoria', 'count']


class ScrapingLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScrapingLocation
        fields = ['id', 'location_name', 'city', 'count']
