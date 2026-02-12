from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProductionEventViewSet,
    StagingEventViewSet,
    EtlRunViewSet,
    EtlErrorViewSet,
    DashboardView,
    ExternalStagingEventViewSet,
)

# Router per API interne (admin) — senza versioning
router = DefaultRouter()
router.register(r'events', ProductionEventViewSet, basename='events')
router.register(r'staging', StagingEventViewSet, basename='staging')
router.register(r'etl-runs', EtlRunViewSet, basename='etl-runs')
router.register(r'etl-errors', EtlErrorViewSet, basename='etl-errors')

# Router per API esterne (OAuth2) — versionato
external_router = DefaultRouter()
external_router.register(r'staging', ExternalStagingEventViewSet, basename='external-staging')

urlpatterns = [
    # /api/events/, /api/staging/, /api/dashboard/ (no versioning)
    path('', include(router.urls)),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),

    # /api/external/v1/staging/, /api/external/v1/staging/bulk/
    # Per aggiungere v2: path('external/v2/', include(external_router_v2.urls))
    path('external/v1/', include(external_router.urls)),
]
