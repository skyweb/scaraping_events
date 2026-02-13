from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import PaginaCittaViewSet, upload_image

router = DefaultRouter()
router.register(r'citta', PaginaCittaViewSet, basename='citta')

urlpatterns = [
    path('upload/', upload_image, name='cms-upload-image'),
    path('', include(router.urls)),
]
