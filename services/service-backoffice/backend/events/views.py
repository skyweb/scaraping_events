from rest_framework import viewsets, status, serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from oauth2_provider.contrib.rest_framework import TokenHasReadWriteScope, TokenHasScope
from rest_framework_tracking.mixins import LoggingMixin
from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from .models import ProductionEvent, StagingEvent, EtlRun, EtlError
from .serializers import (
    ProductionEventSerializer,
    ProductionEventListSerializer,
    StagingEventSerializer,
    StagingEventCreateSerializer,
    EtlRunSerializer,
    EtlErrorSerializer,
    DashboardStatsSerializer,
)


# Serializers per risposte Swagger
class BulkCreateResponseSerializer(drf_serializers.Serializer):
    created = drf_serializers.IntegerField()
    events = StagingEventSerializer(many=True)


class BulkCreateRequestSerializer(drf_serializers.Serializer):
    events = StagingEventCreateSerializer(many=True)


class ClearSourceResponseSerializer(drf_serializers.Serializer):
    deleted = drf_serializers.IntegerField()
    source = drf_serializers.CharField()


class ErrorResponseSerializer(drf_serializers.Serializer):
    error = drf_serializers.CharField()


class ProductionEventViewSet(viewsets.ModelViewSet):
    queryset = ProductionEvent.objects.all()
    serializer_class = ProductionEventSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['city', 'source', 'is_active', 'date_start', 'date_end']
    search_fields = ['title', 'description', 'location_name', 'location_address']
    ordering_fields = ['date_start', 'date_end', 'created_at', 'title', 'city']
    ordering = ['-date_start']

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductionEventListSerializer
        return ProductionEventSerializer

    @action(detail=False, methods=['get'])
    def cities(self, request):
        """Lista delle città disponibili"""
        cities = (
            ProductionEvent.objects
            .values('city')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        return Response(list(cities))

    @action(detail=False, methods=['get'])
    def sources(self, request):
        """Lista delle sorgenti disponibili"""
        sources = (
            ProductionEvent.objects
            .values('source')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        return Response(list(sources))

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle stato attivo/inattivo"""
        event = self.get_object()
        event.is_active = not event.is_active
        event.save()
        return Response({'is_active': event.is_active})


class StagingEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StagingEvent.objects.all()
    serializer_class = StagingEventSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['city', 'source']
    search_fields = ['title', 'description']


class EtlRunViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EtlRun.objects.all()
    serializer_class = EtlRunSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['run_type', 'source', 'status']
    ordering_fields = ['started_at', 'staging_count', 'inserted_count']
    ordering = ['-started_at']


class EtlErrorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EtlError.objects.all()
    serializer_class = EtlErrorSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['error_type', 'source']
    search_fields = ['error_message', 'json_file']
    ordering = ['-created_at']


class DashboardView(APIView):
    """Dashboard con statistiche generali"""

    def get(self, request):
        total_events = ProductionEvent.objects.count()
        active_events = ProductionEvent.objects.filter(is_active=True).count()

        events_by_city = dict(
            ProductionEvent.objects
            .values('city')
            .annotate(count=Count('id'))
            .order_by('-count')
            .values_list('city', 'count')[:10]
        )

        events_by_source = dict(
            ProductionEvent.objects
            .values('source')
            .annotate(count=Count('id'))
            .values_list('source', 'count')
        )

        recent_etl_runs = EtlRun.objects.all()[:5]
        staging_count = StagingEvent.objects.count()

        data = {
            'total_events': total_events,
            'active_events': active_events,
            'events_by_city': events_by_city,
            'events_by_source': events_by_source,
            'recent_etl_runs': EtlRunSerializer(recent_etl_runs, many=True).data,
            'staging_count': staging_count,
        }

        return Response(data)


# =============================================================================
# API ESTERNE (OAuth2 + Tracking)
# =============================================================================

@extend_schema_view(
    list=extend_schema(
        summary="Lista staging events",
        description="Recupera la lista di tutti gli staging events. Richiede scope `read`.",
        tags=["Staging Events"],
    ),
    retrieve=extend_schema(
        summary="Dettaglio staging event",
        description="Recupera i dettagli di un singolo staging event. Richiede scope `read`.",
        tags=["Staging Events"],
    ),
    create=extend_schema(
        summary="Crea staging event",
        description="Crea un nuovo staging event. Richiede scope `write`.",
        tags=["Staging Events"],
        examples=[
            OpenApiExample(
                "Esempio evento",
                value={
                    "uuid": "evt_abc123",
                    "source": "my_service",
                    "title": "Concerto Jazz",
                    "city": "Milano",
                    "description": "Serata di musica jazz dal vivo",
                    "date_start": "2026-02-15",
                    "date_end": "2026-02-15",
                    "time_start": "21:00",
                    "location_name": "Blue Note",
                    "location_address": "Via Borsieri 37, Milano",
                    "price": "25 EUR",
                    "category": ["musica", "jazz", "concerti"]
                },
                request_only=True,
            ),
        ],
    ),
    destroy=extend_schema(
        summary="Elimina staging event",
        description="Elimina uno staging event specifico. Richiede scope `write`.",
        tags=["Staging Events"],
    ),
    update=extend_schema(
        summary="Aggiorna staging event",
        description="Aggiorna completamente uno staging event. Richiede scope `write`.",
        tags=["Staging Events"],
    ),
    partial_update=extend_schema(
        summary="Aggiorna parzialmente staging event",
        description="Aggiorna parzialmente uno staging event. Richiede scope `write`.",
        tags=["Staging Events"],
    ),
)
class ExternalStagingEventViewSet(LoggingMixin, viewsets.ModelViewSet):
    """
    API per servizi esterni - richiede OAuth2 token.

    ## Autenticazione

    Tutte le richieste richiedono un token OAuth2 valido nell'header:
    ```
    Authorization: Bearer <access_token>
    ```

    ## Scopes richiesti

    - `read` - Per operazioni di lettura (GET)
    - `write` - Per operazioni di scrittura (POST, PUT, PATCH, DELETE)
    """
    queryset = StagingEvent.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['city', 'source', 'uuid']
    search_fields = ['title', 'description', 'location_name']
    ordering_fields = ['loaded_at', 'date_start', 'city']
    ordering = ['-loaded_at']

    # Logging settings
    logging_methods = ['POST', 'PUT', 'PATCH', 'DELETE']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated, TokenHasScope]
            self.required_scopes = ['read']
        else:
            permission_classes = [IsAuthenticated, TokenHasScope]
            self.required_scopes = ['write']
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update', 'bulk_create']:
            return StagingEventCreateSerializer
        return StagingEventSerializer

    @extend_schema(
        summary="Bulk create staging events",
        description="""
Crea multipli staging events in una sola richiesta.

**Richiede scope `write`.**

Utile per importare grandi quantità di eventi in modo efficiente.
        """,
        tags=["Bulk Operations"],
        request=BulkCreateRequestSerializer,
        responses={
            201: BulkCreateResponseSerializer,
            400: ErrorResponseSerializer,
        },
        examples=[
            OpenApiExample(
                "Esempio bulk create",
                value={
                    "events": [
                        {
                            "uuid": "evt_001",
                            "source": "my_service",
                            "title": "Evento 1",
                            "city": "Milano"
                        },
                        {
                            "uuid": "evt_002",
                            "source": "my_service",
                            "title": "Evento 2",
                            "city": "Roma"
                        }
                    ]
                },
                request_only=True,
            ),
        ],
    )
    @action(detail=False, methods=['post'])
    def bulk(self, request):
        """Crea multipli staging events in una sola richiesta."""
        events_data = request.data.get('events', [])
        if not events_data:
            return Response(
                {'error': 'No events provided. Expected {"events": [...]}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = StagingEventCreateSerializer(data=events_data, many=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    'created': len(serializer.data),
                    'events': serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Elimina eventi per sorgente",
        description="""
Elimina tutti gli staging events di una specifica sorgente.

**Richiede scope `write`.**

Utile per pulire i dati prima di un nuovo import.
        """,
        tags=["Bulk Operations"],
        parameters=[
            OpenApiParameter(
                name='source',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=True,
                description='Nome della sorgente da eliminare',
                examples=[
                    OpenApiExample('Esempio', value='my_service'),
                ],
            ),
        ],
        responses={
            200: ClearSourceResponseSerializer,
            400: ErrorResponseSerializer,
        },
    )
    @action(detail=False, methods=['delete'])
    def clear_source(self, request):
        """Elimina tutti gli staging events di una specifica sorgente."""
        source = request.query_params.get('source')
        if not source:
            return Response(
                {'error': 'source parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        deleted_count, _ = StagingEvent.objects.filter(source=source).delete()
        return Response({
            'deleted': deleted_count,
            'source': source
        })
