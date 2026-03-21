from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProductionEventViewSet,
    EtlRunViewSet,
    EtlErrorViewSet,
    DashboardView,
    ExternalEventViewSet,
)

# Router per API interne (admin)
router = DefaultRouter()
router.register(r'events', ProductionEventViewSet, basename='events')
router.register(r'etl-runs', EtlRunViewSet, basename='etl-runs')
router.register(r'etl-errors', EtlErrorViewSet, basename='etl-errors')

# Router per API esterne — /api/v1/events/
external_router = DefaultRouter()
external_router.register(r'', ExternalEventViewSet, basename='external-events')

urlpatterns = [
    # API interne: /api/events/, /api/dashboard/
    path('', include(router.urls)),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),

    # API esterne versionate: /api/v1/events/
    path('v1/events/', include(external_router.urls)),
]
