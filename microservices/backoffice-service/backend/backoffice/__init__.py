from .celery import app as celery_app
from .otel import init_otel

init_otel()

__all__ = ('celery_app',)
