import logging

from celery import shared_task
from django.db import OperationalError
from opentelemetry import trace
from opentelemetry.trace import StatusCode

from etl.tracing import log_trace_event

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
    span.set_attribute("bulk.spider", spider_name)
    span.set_attribute("bulk.total_events", len(events_data))

    log_trace_event(
        'celery.processing',
        f'Celery task avviato: {len(events_data)} eventi da {spider_name}',
        service='backoffice-celery-worker',
        metadata={'spider': spider_name, 'events_count': len(events_data), 'task_id': self.request.id},
    )

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
                "event.index": idx,
            })
        else:
            failed_events.append({
                'index': idx,
                'errors': serializer.errors,
                'original_data': data,
            })
            span.add_event("event.validation_failed", attributes={
                "event.uuid": data.get("uuid", ""),
                "event.index": idx,
                "event.errors": str(serializer.errors)[:200],
            })
            logger.warning(
                "Validazione fallita: uuid=%s index=%d errors=%s",
                data.get("uuid", ""), idx, str(serializer.errors)[:200]
            )

    if not valid_instances:
        span.set_attribute("bulk.created_count", 0)
        span.set_attribute("bulk.failed_count", len(failed_events))
        span.set_status(StatusCode.ERROR, f"Tutti i {len(failed_events)} eventi falliti in validazione")
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
        span.set_status(StatusCode.ERROR, f"OperationalError: {exc}")
        span.add_event("bulk.retry", attributes={
            "retry.attempt": self.request.retries + 1,
            "retry.error": str(exc)[:200],
        })
        logger.warning(f"bulk_create OperationalError, retrying: {exc}")
        raise self.retry(exc=exc)
    except Exception as exc:
        # 3. Fallback: save singoli
        span.add_event("bulk.fallback_to_individual", attributes={
            "fallback.reason": str(exc)[:200],
        })
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
                span.add_event("event.save_failed", attributes={
                    "event.uuid": str(instance.uuid),
                    "event.index": idx,
                    "event.error": str(save_exc)[:200],
                })

    # Attributi finali per filtraggio in Jaeger
    span.set_attribute("bulk.created_count", created_count)
    span.set_attribute("bulk.failed_count", len(failed_events))
    span.set_attribute("bulk.validated_count", len(valid_instances))

    if failed_events:
        span.set_status(
            StatusCode.ERROR,
            f"{len(failed_events)} eventi falliti su {len(events_data)}"
        )
        failed_uuids = [e.get('original_data', {}).get('uuid', '?') for e in failed_events]
        log_trace_event(
            'celery.partial_failure',
            f'{len(failed_events)} eventi falliti su {len(events_data)}',
            level='error',
            service='backoffice-celery-worker',
            metadata={
                'spider': spider_name,
                'task_id': self.request.id,
                'created_count': created_count,
                'failed_count': len(failed_events),
                'failed_uuids': failed_uuids[:20],
            },
        )
    else:
        span.set_status(StatusCode.OK)
        log_trace_event(
            'celery.completed',
            f'{created_count} eventi creati da {spider_name}',
            service='backoffice-celery-worker',
            metadata={'spider': spider_name, 'task_id': self.request.id, 'created_count': created_count},
        )

    return {
        'spider_name': spider_name,
        'created_count': created_count,
        'failed_count': len(failed_events),
        'failed_events': failed_events,
    }
