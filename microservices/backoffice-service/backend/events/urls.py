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

# Router per API interne (admin)
router = DefaultRouter()
router.register(r'events', ProductionEventViewSet, basename='events')
router.register(r'staging', StagingEventViewSet, basename='staging')
router.register(r'etl-runs', EtlRunViewSet, basename='etl-runs')
router.register(r'etl-errors', EtlErrorViewSet, basename='etl-errors')

# Router per API esterne (OAuth2) — /api/v1/events/staging/
external_router = DefaultRouter()
external_router.register(r'staging', ExternalStagingEventViewSet, basename='external-staging')

urlpatterns = [
    # API interne: /api/events/, /api/staging/, /api/dashboard/
    path('', include(router.urls)),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),

    # API esterne versionate: /api/v1/events/staging/
    # Per aggiungere v2: path('v1/events/', include(external_router_v2.urls))
    path('v1/events/', include(external_router.urls)),
]
