from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from backoffice.authentication import HasKeycloakScope
from django.db.models import Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from celery.result import AsyncResult
from opentelemetry import trace
from etl.tracing import log_trace_event

from .models import ProductionEvent, StagingEvent
from etl.models import EtlRun, EtlError
from .serializers import (
    ProductionEventSerializer,
    ProductionEventListSerializer,
    StagingEventSerializer,
    StagingEventBulkResponseSerializer,
    StagingEventScrapingSerializer,
    StagingEventLegacySerializer,
    EtlRunSerializer,
    EtlErrorSerializer,
    DashboardStatsSerializer,
    FailedEventSerializer,
    BulkProcessResponseSerializer,
    BulkCreateResponseSerializer,
    BulkCreateRequestSerializer,
    ClearSourceResponseSerializer,
    BulkAcceptedResponseSerializer,
    BulkTaskStatusResponseSerializer,
    ErrorResponseSerializer,
    CityCountSerializer,
    SourceCountSerializer,
    ToggleActiveResponseSerializer,
    get_plan_serializer_class,
)


@extend_schema_view(
    list=extend_schema(
        summary="Lista production events",
        description="Recupera la lista paginata degli eventi in produzione. Supporta filtri, ricerca e ordinamento.",
        tags=["Production Events"],
    ),
    retrieve=extend_schema(
        summary="Dettaglio production event",
        description="Recupera tutti i dettagli di un singolo evento in produzione.",
        tags=["Production Events"],
    ),
    create=extend_schema(
        summary="Crea production event",
        description="Crea un nuovo evento in produzione.",
        tags=["Production Events"],
    ),
    update=extend_schema(
        summary="Aggiorna production event",
        description="Aggiorna completamente un evento in produzione.",
        tags=["Production Events"],
    ),
    partial_update=extend_schema(
        summary="Aggiorna parzialmente production event",
        description="Aggiorna parzialmente un evento in produzione.",
        tags=["Production Events"],
    ),
    destroy=extend_schema(
        summary="Elimina production event",
        description="Elimina un evento in produzione.",
        tags=["Production Events"],
    ),
)
class ProductionEventViewSet(viewsets.ModelViewSet):
    """ViewSet CRUD per gli eventi in produzione con filtri, ricerca e ordinamento."""
    queryset = ProductionEvent.objects.all()
    serializer_class = ProductionEventSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['city', 'source', 'is_active', 'date_start', 'date_end']
    search_fields = ['title', 'description', 'location_name', 'location_address']
    ordering_fields = ['date_start', 'date_end', 'created_at', 'title', 'city']
    ordering = ['-date_start']

    def get_serializer_class(self):
        """Restituisce il serializer leggero per la lista, completo per il dettaglio."""
        if self.action == 'list':
            return ProductionEventListSerializer
        return ProductionEventSerializer

    @extend_schema(
        summary="Citta' disponibili",
        description="Restituisce la lista delle citta' con il conteggio degli eventi per ciascuna.",
        tags=["Production Events"],
        responses={200: CityCountSerializer(many=True)},
    )
    @action(detail=False, methods=['get'])
    def cities(self, request, **kwargs):
        """Lista delle città disponibili"""
        cities = (
            ProductionEvent.objects
            .values('city')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        return Response(list(cities))

    @extend_schema(
        summary="Sorgenti disponibili",
        description="Restituisce la lista delle sorgenti dati con il conteggio degli eventi per ciascuna.",
        tags=["Production Events"],
        responses={200: SourceCountSerializer(many=True)},
    )
    @action(detail=False, methods=['get'])
    def sources(self, request, **kwargs):
        """Lista delle sorgenti disponibili"""
        sources = (
            ProductionEvent.objects
            .values('source')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        return Response(list(sources))

    @extend_schema(
        summary="Toggle attivo/inattivo",
        description="Inverte lo stato `is_active` dell'evento specificato.",
        tags=["Production Events"],
        request=None,
        responses={200: ToggleActiveResponseSerializer},
    )
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None, **kwargs):
        """Toggle stato attivo/inattivo"""
        event = self.get_object()
        event.is_active = not event.is_active
        event.save()
        return Response({'is_active': event.is_active})


@extend_schema_view(
    list=extend_schema(
        summary="Lista staging events",
        description="Recupera la lista paginata degli eventi in staging (pre-validazione).",
        tags=["Staging Events (Internal)"],
    ),
    retrieve=extend_schema(
        summary="Dettaglio staging event",
        description="Recupera i dettagli di un singolo evento in staging.",
        tags=["Staging Events (Internal)"],
    ),
)
class StagingEventViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet in sola lettura per gli staging events (API interne admin)."""
    queryset = StagingEvent.objects.all()
    serializer_class = StagingEventSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['city_name', 'source']
    search_fields = ['title', 'description']


@extend_schema_view(
    list=extend_schema(
        summary="Lista ETL runs",
        description="Recupera lo storico delle esecuzioni ETL con durata, conteggi e stato.",
        tags=["ETL"],
    ),
    retrieve=extend_schema(
        summary="Dettaglio ETL run",
        description="Recupera i dettagli di una singola esecuzione ETL.",
        tags=["ETL"],
    ),
)
class EtlRunViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet in sola lettura per lo storico delle esecuzioni ETL."""
    queryset = EtlRun.objects.all()
    serializer_class = EtlRunSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['run_type', 'source', 'status']
    ordering_fields = ['started_at', 'staging_count', 'inserted_count']
    ordering = ['-started_at']


@extend_schema_view(
    list=extend_schema(
        summary="Lista ETL errors",
        description="Recupera lo storico degli errori ETL con tipo, sorgente e messaggio.",
        tags=["ETL"],
    ),
    retrieve=extend_schema(
        summary="Dettaglio ETL error",
        description="Recupera i dettagli di un singolo errore ETL.",
        tags=["ETL"],
    ),
)
class EtlErrorViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet in sola lettura per lo storico degli errori ETL."""
    queryset = EtlError.objects.all()
    serializer_class = EtlErrorSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['error_type', 'source']
    search_fields = ['error_message', 'json_file']
    ordering = ['-created_at']


class DashboardView(APIView):
    """Dashboard con statistiche generali"""

    @extend_schema(
        summary="Statistiche dashboard",
        description="Restituisce statistiche aggregate: totale eventi, eventi attivi, distribuzione per citta'/sorgente, ultimi ETL runs e conteggio staging.",
        tags=["Dashboard"],
        responses={200: DashboardStatsSerializer},
    )
    def get(self, request, **kwargs):
        """Restituisce statistiche aggregate per la dashboard: totali, distribuzione e staging."""
        # Aggregazione in una singola query per total + active
        counts = ProductionEvent.objects.aggregate(
            total_events=Count('id'),
            active_events=Count('id', filter=Q(is_active=True)),
        )

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
            'total_events': counts['total_events'],
            'active_events': counts['active_events'],
            'events_by_city': events_by_city,
            'events_by_source': events_by_source,
            'recent_etl_runs': EtlRunSerializer(recent_etl_runs, many=True).data,
            'staging_count': staging_count,
        }

        return Response(data)


# =============================================================================
# API ESTERNE
# =============================================================================

from django.conf import settings as django_settings

CACHE_TTL = getattr(django_settings, 'API_CACHE_TTL', 60 * 60)
CACHE_VERSION_KEY = "api_external_cache_version"


def _get_cache_version() -> int:
    """Ritorna la versione corrente della cache API external."""
    from django.core.cache import cache
    version = cache.get(CACHE_VERSION_KEY)
    if version is None:
        cache.set(CACHE_VERSION_KEY, 1, timeout=None)
        return 1
    return version


def _invalidate_external_cache():
    """Invalida la cache incrementando il version counter."""
    from django.core.cache import cache
    try:
        cache.incr(CACHE_VERSION_KEY)
    except ValueError:
        cache.set(CACHE_VERSION_KEY, 1, timeout=None)


class PlanFieldFilterMixin:
    """Mixin che filtra i campi della response in base al piano API del consumer
    e aggiunge cache Redis con Vary sul piano."""

    def _get_consumer_plan(self) -> str | None:
        """Legge il piano dal header X-Consumer-Plan (iniettato da APISIX)."""
        auth_info = getattr(self.request, "auth", None)
        if isinstance(auth_info, dict):
            return auth_info.get("plan")
        return self.request.META.get("HTTP_X_CONSUMER_PLAN")

    def get_serializer_class(self):
        """Seleziona il serializer filtrato in base al piano API del consumer."""
        # Per azioni di lettura (list/retrieve), filtra i campi in base al piano
        if self.action in ("list", "retrieve"):
            plan = self._get_consumer_plan()
            if plan:
                return get_plan_serializer_class(plan)
        return super().get_serializer_class()

    def _cached_key_prefix(self) -> str:
        """Genera un key_prefix che include la versione cache e il piano."""
        plan = self._get_consumer_plan() or "noplan"
        version = _get_cache_version()
        return f"api_ext_v{version}_{plan}"

    def list(self, request, *args, **kwargs):
        """Lista con cache Redis, variata per piano API e versione."""
        from django.views.decorators.cache import cache_page
        key_prefix = self._cached_key_prefix()
        decorator = cache_page(CACHE_TTL, key_prefix=key_prefix)
        response_fn = decorator(lambda r, *a, **k: super(PlanFieldFilterMixin, self).list(r, *a, **k))
        return response_fn(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """Dettaglio con cache Redis, variata per piano API e versione."""
        from django.views.decorators.cache import cache_page
        key_prefix = self._cached_key_prefix()
        decorator = cache_page(CACHE_TTL, key_prefix=key_prefix)
        response_fn = decorator(lambda r, *a, **k: super(PlanFieldFilterMixin, self).retrieve(r, *a, **k))
        return response_fn(request, *args, **kwargs)

    def perform_create(self, serializer):
        """Salva il nuovo oggetto e invalida la cache API external."""
        super().perform_create(serializer)
        _invalidate_external_cache()

    def perform_update(self, serializer):
        """Aggiorna l'oggetto e invalida la cache API external."""
        super().perform_update(serializer)
        _invalidate_external_cache()

    def perform_destroy(self, instance):
        """Elimina l'oggetto e invalida la cache API external."""
        super().perform_destroy(instance)
        _invalidate_external_cache()


@extend_schema_view(
    list=extend_schema(
        summary="Lista staging events",
        description="Recupera la lista di tutti gli staging events. Richiede permesso `events:read`.",
        tags=["Staging Events"],
    ),
    retrieve=extend_schema(
        summary="Dettaglio staging event",
        description="Recupera i dettagli di un singolo staging event. Richiede permesso `events:read`.",
        tags=["Staging Events"],
    ),
    create=extend_schema(
        summary="Crea staging event",
        description="""
Crea un nuovo staging event. Richiede permesso `events:create`.

**Campi obbligatori:** `uuid`, `source`, `title`

Tutti gli altri campi sono opzionali. Il campo `uuid` deve essere univoco
per sorgente (tipicamente un hash di title + date_start + location_name).
        """,
        tags=["Staging Events"],
        examples=[
            OpenApiExample(
                "Evento completo",
                summary="Evento con tutti i campi compilati",
                value={
                    "uuid": "a1b2c3d4e5f6",
                    "content_hash": "f6e5d4c3b2a1",
                    "source": "city_today",
                    "url": "https://www.example.com/eventi/concerto-jazz-milano",
                    "title": "Concerto Jazz al Blue Note",
                    "description": "Una serata di musica jazz dal vivo con artisti internazionali. Aperitivo dalle 19:30, concerto dalle 21:00.",
                    "category": ["musica", "jazz", "concerti", "nightlife"],
                    "image_url": "https://www.example.com/img/jazz-night.jpg",
                    "city": "milano",
                    "location_name": "Blue Note Milano",
                    "location_address": "Via Borsieri 37, 20159 Milano MI",
                    "price": "25,00 EUR + prevendita",
                    "website": "https://www.bluenotemilano.com",
                    "date_start": "2026-02-15",
                    "date_end": "2026-02-15",
                    "time_start": "21:00:00",
                    "time_end": "23:30:00",
                    "time_info": "Apertura porte ore 19:30",
                    "schedule": "Venerdi e Sabato",
                    "weekdays": "fri,sat",
                    "raw_data": {
                        "original_id": "12345",
                        "scraped_from": "city_today",
                        "extra_field": "valore originale"
                    },
                    "scraped_at": "2026-02-05T14:30:00Z"
                },
                request_only=True,
            ),
            OpenApiExample(
                "Evento minimo",
                summary="Solo i campi obbligatori",
                value={
                    "uuid": "b2c3d4e5f6a1",
                    "source": "city_today",
                    "title": "Mercatino di Natale",
                    "city": "bologna",
                    "date_start": "2026-12-01",
                    "date_end": "2026-12-24"
                },
                request_only=True,
            ),
        ],
    ),
    destroy=extend_schema(
        summary="Elimina staging event",
        description="Elimina uno staging event specifico. Richiede permesso `events:delete`.",
        tags=["Staging Events"],
    ),
    update=extend_schema(
        summary="Aggiorna staging event",
        description="Aggiorna completamente uno staging event. Richiede permesso `events:update`.",
        tags=["Staging Events"],
    ),
    partial_update=extend_schema(
        summary="Aggiorna parzialmente staging event",
        description="Aggiorna parzialmente uno staging event. Richiede permesso `events:update`.",
        tags=["Staging Events"],
    ),
)
class ExternalStagingEventViewSet(PlanFieldFilterMixin, viewsets.ModelViewSet):
    """
    API esterne per la gestione degli staging events.

    ## Autenticazione

    Tutte le richieste richiedono un token Bearer o API key:
    ```
    Authorization: Bearer <access_token>
    ```

    ## Permessi

    I permessi sono gestiti dalla matrice API Consumers:
    - `events:read` - Lettura (GET)
    - `events:create` - Creazione singola e bulk (POST)
    - `events:update` - Aggiornamento (PUT, PATCH)
    - `events:delete` - Eliminazione (DELETE)
    """

    queryset = StagingEvent.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['city_name', 'source', 'uuid']
    search_fields = ['title', 'description', 'location_name']
    ordering_fields = ['created_at', 'date_start', 'city_name']
    ordering = ['-created_at']

    def get_permissions(self):
        """Associa ogni azione al permesso richiesto (es. events:read, events:create)."""
        action_map = {
            'list': 'read',
            'retrieve': 'read',
            'create': 'create',
            'update': 'update',
            'partial_update': 'update',
            'destroy': 'delete',
            'bulk': 'create',
            'bulk_status': 'read',
            'clear_source': 'delete',
        }
        action = action_map.get(self.action, 'read')
        self.required_scopes = [f'events:{action}']
        return [HasKeycloakScope()]

    def get_serializer_class(self):
        """Restituisce il serializer scraping per le scritture, quello standard per le letture."""
        if self.action in ['create', 'update', 'partial_update', 'bulk_create']:
            return StagingEventScrapingSerializer
        return StagingEventSerializer

    @extend_schema(
        summary="Bulk create staging events",
        description="""
Crea multipli staging events in una sola richiesta.

**Richiede permesso `events:create`.**

**Modalita':**
- **Async (default):** Il batch viene processato in background tramite Celery.
  Ritorna 202 Accepted con un `task_id` per monitorare lo stato.
- **Sync (`?sync=true`):** Comportamento sincrono originale, processa tutto nella richiesta.
        """,
        tags=["Bulk Operations"],
        request=BulkCreateRequestSerializer,
        parameters=[
            OpenApiParameter(
                name='sync',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Se true, processa il batch in modo sincrono (default: false)',
            ),
        ],
        responses={
            200: BulkProcessResponseSerializer,
            201: BulkProcessResponseSerializer,
            202: BulkAcceptedResponseSerializer,
            400: BulkProcessResponseSerializer,
        },
        examples=[
            OpenApiExample(
                "Bulk con eventi completi",
                summary="Due eventi con tutti i campi compilati",
                value={
                    "events": [
                        {
                            "uuid": "a1b2c3d4e5f6",
                            "content_hash": "f6e5d4c3b2a1",
                            "source": "city_today",
                            "url": "https://www.example.com/eventi/concerto-jazz-milano",
                            "title": "Concerto Jazz al Blue Note",
                            "description": "Una serata di musica jazz dal vivo con artisti internazionali.",
                            "category": ["musica", "jazz", "concerti"],
                            "image_url": "https://www.example.com/img/jazz-night.jpg",
                            "city": "milano",
                            "location_name": "Blue Note Milano",
                            "location_address": "Via Borsieri 37, 20159 Milano MI",
                            "price": "25,00 EUR",
                            "website": "https://www.bluenotemilano.com",
                            "date_start": "2026-02-15",
                            "date_end": "2026-02-15",
                            "time_start": "21:00:00",
                            "time_end": "23:30:00",
                            "time_info": "Apertura porte ore 19:30",
                            "schedule": "Venerdi e Sabato",
                            "weekdays": "fri,sat",
                            "raw_data": {"original_id": "12345"},
                            "scraped_at": "2026-02-05T14:30:00Z"
                        },
                        {
                            "uuid": "b2c3d4e5f6a1",
                            "content_hash": "a1f6e5d4c3b2",
                            "source": "city_today",
                            "url": "https://www.example.com/eventi/mostra-caravaggio-roma",
                            "title": "Mostra Caravaggio - Luci e Ombre",
                            "description": "Esposizione dedicata alle opere di Caravaggio con percorso multimediale.",
                            "category": ["arte", "mostre", "cultura"],
                            "image_url": "https://www.example.com/img/caravaggio.jpg",
                            "city": "roma",
                            "location_name": "Palazzo delle Esposizioni",
                            "location_address": "Via Nazionale 194, 00184 Roma RM",
                            "price": "15,00 EUR",
                            "website": "https://www.palazzoesposizioni.it",
                            "date_start": "2026-02-01",
                            "date_end": "2026-04-30",
                            "time_start": "10:00:00",
                            "time_end": "20:00:00",
                            "time_info": "Ultimo ingresso ore 19:00",
                            "schedule": "Da martedi a domenica",
                            "weekdays": "tue,wed,thu,fri,sat,sun",
                            "raw_data": {"original_id": "67890"},
                            "scraped_at": "2026-02-05T14:30:00Z"
                        }
                    ]
                },
                request_only=True,
            ),
            OpenApiExample(
                "Bulk con eventi minimi",
                summary="Due eventi con solo i campi obbligatori",
                value={
                    "events": [
                        {
                            "uuid": "evt_001",
                            "source": "city_today",
                            "title": "Mercatino di Natale",
                            "city": "bologna",
                            "date_start": "2026-12-01",
                            "date_end": "2026-12-24"
                        },
                        {
                            "uuid": "evt_002",
                            "source": "city_today",
                            "title": "Sagra del Tartufo",
                            "city": "firenze",
                            "date_start": "2026-03-10",
                            "date_end": "2026-03-12"
                        }
                    ]
                },
                request_only=True,
            ),
            OpenApiExample(
                "Bulk con eventi parzialmente validi",
                summary="Un evento valido e uno non valido",
                value={
                    "events": [
                        {
                            "uuid": "evt_003",
                            "source": "test_source",
                            "title": "Evento Valido di Prova",
                            "city": "milano",
                            "date_start": "2026-03-01"
                        },
                        {
                            "uuid": "evt_004",
                            "source": "test_source",
                            "city": "roma",
                            "date_start": "2026-03-02"
                        }
                    ]
                },
                request_only=True,
            ),
        ],
    )
    @action(detail=False, methods=['post'])
    def bulk(self, request, **kwargs):
        """Crea multipli staging events. Default: async via Celery. ?sync=true per sincrono."""
        events_data = request.data.get('events', [])
        if not events_data:
            return Response(
                {'error': 'No events provided. Expected {"events": [...]}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        spider_name = request.data.get('spider', 'unknown')
        batch_file = request.data.get('batch_file') or request.data.get('storage_path')
        span = trace.get_current_span()
        span.set_attribute("bulk.events_count", len(events_data))
        span.set_attribute("bulk.spider", spider_name)

        sync_mode = request.query_params.get('sync', 'false').lower() in ('true', '1', 'yes')
        span.set_attribute("bulk.mode", "sync" if sync_mode else "async")

        log_trace_event(
            'bulk.received',
            f'Ricevuti {len(events_data)} eventi da {spider_name}',
            metadata={'spider': spider_name, 'events_count': len(events_data), 'mode': 'sync' if sync_mode else 'async'},
        )

        # Inietta batch_file in meta di ogni evento (se non già presente)
        if batch_file:
            for event in events_data:
                meta = event.get('meta') or {}
                if not meta.get('batch_file'):
                    meta['batch_file'] = batch_file
                    event['meta'] = meta

        if sync_mode:
            response = self._bulk_sync(events_data, span)
            _invalidate_external_cache()
            return response

        # Async mode: dispatch to Celery
        from .tasks import process_bulk_events
        task = process_bulk_events.apply_async(
            args=[events_data],
            kwargs={'spider_name': spider_name},
        )
        span.set_attribute("celery.task_id", task.id)
        span.add_event("bulk.dispatched", attributes={
            "celery.task_id": task.id,
            "bulk.events_count": len(events_data),
            "bulk.spider": spider_name,
        })
        log_trace_event(
            'bulk.dispatched',
            f'Batch inviato a Celery: task_id={task.id}',
            metadata={'task_id': task.id, 'spider': spider_name, 'events_count': len(events_data)},
        )
        return Response(
            {
                'task_id': task.id,
                'status': 'PENDING',
                'message': f'Batch of {len(events_data)} events accepted for processing.',
                'spider': spider_name,
            },
            status=status.HTTP_202_ACCEPTED,
        )

    def _bulk_sync(self, events_data, span=None):
        """Logica sincrona per il bulk create.

        Rileva il formato automaticamente:
        - Formato event scraping (con 'uuid', 'city', 'dates'): usa StagingEventScrapingSerializer
        - Formato legacy (nested con 'details'): usa StagingEventLegacySerializer
        """
        from opentelemetry.trace import StatusCode

        if span is None:
            span = trace.get_current_span()

        successful_events = []
        failed_events = []

        for index, item_data in enumerate(events_data):
            event_uuid = item_data.get('uuid', f'index_{index}')

            # Rileva formato in base alla struttura delle chiavi
            if 'details' in item_data:
                serializer = StagingEventLegacySerializer(data=item_data)
            else:
                serializer = StagingEventScrapingSerializer(data=item_data)

            if serializer.is_valid():
                try:
                    instance = serializer.save()
                    successful_events.append(instance)
                    span.add_event("event.created", attributes={
                        "event.uuid": str(instance.uuid),
                        "event.title": str(instance.title)[:80],
                        "event.index": index,
                    })
                except Exception as e:
                    failed_events.append({
                        'original_data': item_data,
                        'errors': {'non_field_errors': [str(e)]},
                        'index': index
                    })
                    span.add_event("event.save_failed", attributes={
                        "event.uuid": event_uuid,
                        "event.index": index,
                        "event.error": str(e)[:200],
                    })
            else:
                failed_events.append({
                    'original_data': item_data,
                    'errors': serializer.errors,
                    'index': index
                })
                span.add_event("event.validation_failed", attributes={
                    "event.uuid": event_uuid,
                    "event.index": index,
                    "event.errors": str(serializer.errors)[:200],
                })

        span.set_attribute("bulk.created_count", len(successful_events))
        span.set_attribute("bulk.failed_count", len(failed_events))

        if failed_events:
            span.set_status(StatusCode.ERROR, f"{len(failed_events)} eventi falliti su {len(events_data)}")
            # Log errori individuali nel trace DB
            failed_uuids = [e.get('original_data', {}).get('uuid', '?') for e in failed_events]
            log_trace_event(
                'bulk.partial_failure',
                f'{len(failed_events)} eventi falliti su {len(events_data)}',
                level='error',
                metadata={
                    'created_count': len(successful_events),
                    'failed_count': len(failed_events),
                    'failed_uuids': failed_uuids[:20],
                    'failed_details': [{
                        'uuid': e.get('original_data', {}).get('uuid', '?'),
                        'index': e.get('index'),
                        'errors': str(e.get('errors', ''))[:200],
                    } for e in failed_events[:10]],
                },
            )
        else:
            log_trace_event(
                'bulk.completed',
                f'{len(successful_events)} eventi creati (sync)',
                metadata={'created_count': len(successful_events)},
            )

        if successful_events and not failed_events:
            status_code = status.HTTP_201_CREATED
        elif not successful_events and failed_events:
            status_code = status.HTTP_400_BAD_REQUEST
        else:
            status_code = status.HTTP_200_OK

        return Response({
            'successful_events': StagingEventBulkResponseSerializer(successful_events, many=True).data,
            'failed_events': failed_events,
            'created_count': len(successful_events),
            'failed_count': len(failed_events),
        }, status=status_code)

    @extend_schema(
        summary="Stato bulk task asincrono",
        description="""
Controlla lo stato di un task di bulk create asincrono.

**Richiede permesso `events:read`.**

**Stati possibili:** PENDING, STARTED, SUCCESS, FAILURE
        """,
        tags=["Bulk Operations"],
        parameters=[
            OpenApiParameter(
                name='task_id',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                required=True,
                description='ID del task Celery',
            ),
        ],
        responses={
            200: BulkTaskStatusResponseSerializer,
        },
    )
    @action(detail=False, methods=['get'], url_path='bulk-status/(?P<task_id>[^/.]+)')
    def bulk_status(self, request, task_id=None, **kwargs):
        """Controlla lo stato di un task di bulk create asincrono."""
        result = AsyncResult(task_id)

        response_data = {
            'task_id': task_id,
            'status': result.status,
            'result': None,
        }

        if result.ready():
            if result.successful():
                response_data['result'] = result.result
            else:
                response_data['result'] = str(result.result)

        return Response(response_data)


    @extend_schema(
        summary="Elimina eventi per sorgente",
        description="""
Elimina tutti gli staging events di una specifica sorgente.

**Richiede permesso `events:delete`.**

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
    def clear_source(self, request, **kwargs):
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
