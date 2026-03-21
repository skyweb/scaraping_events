from django.urls import path
from .views import IngestionView, BulkIngestionView

urlpatterns = [
    path('ingestion/', IngestionView.as_view(), name='comuni-ingestion'),
    path('ingestion/bulk/', BulkIngestionView.as_view(), name='comuni-ingestion-bulk'),
]
