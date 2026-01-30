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

# Router per API esterne (OAuth2)
external_router = DefaultRouter()
external_router.register(r'staging', ExternalStagingEventViewSet, basename='external-staging')

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),

    # API esterne con OAuth2
    path('external/', include(external_router.urls)),
]
