from django.urls import path

from ai_transform.views import models_view, transform_file_view, transform_single_view

urlpatterns = [
    path("file/", transform_file_view, name="ai-transform-file"),
    path("event/", transform_single_view, name="ai-transform-event"),
    path("models/", models_view, name="ai-transform-models"),
]
