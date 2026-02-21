from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter

from .models import ScrapingWebsite, ScrapingCategory, ScrapingLocation
from .serializers import (
    ScrapingWebsiteSerializer,
    ScrapingCategorySerializer,
    ScrapingLocationSerializer,
)


@extend_schema_view(
    list=extend_schema(
        summary="Lista portali web scrapati",
        tags=["Scraping"],
        parameters=[
            OpenApiParameter("is_active", bool, description="Filtra per stato attivo"),
            OpenApiParameter("cms", str, description="Filtra per tipo CMS (drupal, wordpress, custom, api_rest)"),
        ],
    ),
    retrieve=extend_schema(
        summary="Dettaglio portale web",
        tags=["Scraping"],
    ),
)
class ScrapingWebsiteViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Portali web configurati per lo scraping eventi."""
    queryset = ScrapingWebsite.objects.all()
    serializer_class = ScrapingWebsiteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if is_active := self.request.query_params.get('is_active'):
            qs = qs.filter(is_active=is_active.lower() == 'true')
        if cms := self.request.query_params.get('cms'):
            qs = qs.filter(cms=cms)
        return qs


@extend_schema_view(
    list=extend_schema(
        summary="Lista categorie eventi aggregate",
        tags=["Scraping"],
    ),
)
class ScrapingCategoryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Categorie uniche estratte da tutti gli eventi scrapati."""
    queryset = ScrapingCategory.objects.all()
    serializer_class = ScrapingCategorySerializer
    permission_classes = [IsAuthenticated]


@extend_schema_view(
    list=extend_schema(
        summary="Lista location eventi aggregate",
        tags=["Scraping"],
        parameters=[
            OpenApiParameter("city", str, description="Filtra per città"),
        ],
    ),
    retrieve=extend_schema(
        summary="Dettaglio location",
        tags=["Scraping"],
    ),
)
class ScrapingLocationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Location uniche estratte da tutti gli eventi scrapati."""
    queryset = ScrapingLocation.objects.all()
    serializer_class = ScrapingLocationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if city := self.request.query_params.get('city'):
            qs = qs.filter(city__icontains=city)
        return qs
