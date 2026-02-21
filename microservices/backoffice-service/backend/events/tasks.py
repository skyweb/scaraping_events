import logging

from celery import shared_task
from django.db import OperationalError
from opentelemetry import trace

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10, acks_late=True)
def process_bulk_events(self, events_data, spider_name='unknown'):
    """
    Processa un batch di staging events in modo asincrono.

    1. Valida ogni item con StagingEventCreateSerializer
    2. Usa bulk_create per inserire tutti gli item validi (1 query DB)
    3. Retry automatico su OperationalError (max 3 tentativi)
    4. Fallback a save singoli se bulk_create fallisce

    Args:
        events_data: lista di dict con i dati degli eventi
        spider_name: nome dello spider che ha generato il batch

    Returns:
        dict con spider_name, created_count, failed_count, failed_events
    """
    from .serializers import StagingEventScrapingSerializer
    from .models import StagingEvent

    logger.info(f"Processing bulk events from spider: {spider_name} ({len(events_data)} events)")

    span = trace.get_current_span()

    valid_instances = []
    failed_events = []

    # 1. Validate each item
    for idx, data in enumerate(events_data):
        serializer = StagingEventScrapingSerializer(data=data)
        if serializer.is_valid():
            valid_instances.append(StagingEvent(**serializer.validated_data))
            span.add_event("event.validated", attributes={
                "event.uuid": data.get("uuid", ""),
                "event.title": str(data.get("title", ""))[:80],
            })
        else:
            failed_events.append({
                'index': idx,
                'errors': serializer.errors,
                'original_data': data,
            })
            span.add_event("event.validation_failed", attributes={
                "event.uuid": data.get("uuid", ""),
                "event.errors": str(serializer.errors)[:200],
            })

    if not valid_instances:
        return {
            'spider_name': spider_name,
            'created_count': 0,
            'failed_count': len(failed_events),
            'failed_events': failed_events,
        }

    # 2. Bulk create (1 query DB)
    try:
        created = StagingEvent.objects.bulk_create(valid_instances)
        created_count = len(created)
        # Span events + log per ogni evento creato (cercabili in Jaeger/Loki per UUID)
        for instance in created:
            span.add_event("event.created", attributes={
                "event.uuid": str(instance.uuid),
                "event.title": str(instance.title)[:80],
            })
            logger.info(f"Evento creato: uuid={instance.uuid} title={str(instance.title)[:80]}")
    except OperationalError as exc:
        logger.warning(f"bulk_create OperationalError, retrying: {exc}")
        raise self.retry(exc=exc)
    except Exception as exc:
        # 3. Fallback: save singoli
        logger.warning(f"bulk_create failed ({exc}), falling back to individual saves")
        created_count = 0
        for idx, instance in enumerate(valid_instances):
            try:
                instance.save()
                created_count += 1
            except Exception as save_exc:
                failed_events.append({
                    'index': idx,
                    'errors': {'non_field_errors': [str(save_exc)]},
                    'original_data': events_data[idx],
                })

    return {
        'spider_name': spider_name,
        'created_count': created_count,
        'failed_count': len(failed_events),
        'failed_events': failed_events,
    }
