import logging

from celery import shared_task
from django.db import OperationalError
from opentelemetry import trace
from opentelemetry.trace import StatusCode

from etl.tracing import log_trace_event

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=1, acks_late=True)
def recompute_rank_scores(self) -> dict:
    """
    Ricalcola rank_score per tutti gli eventi attivi e disattiva gli scaduti.
    Da schedulare periodicamente via Celery Beat (es. ogni ora).
    """
    from django.utils import timezone
    from .models import Event

    now = timezone.now()

    # Disattiva eventi scaduti (date_end passata)
    expired = Event.objects.filter(
        is_active=True,
        date_end__isnull=False,
        date_end__lt=now,
    ).update(is_active=False, deleted_by='system', deleted_at=now)
    if expired:
        logger.info("Eventi scaduti disattivati: %d", expired)

    # Ricalcola rank_score per gli eventi ancora attivi
    events = Event.objects.filter(is_active=True)
    total = events.count()
    updated = 0
    batch = []

    for event in events.iterator(chunk_size=500):
        new_score = event.compute_rank_score()
        if new_score != event.rank_score:
            event.rank_score = new_score
            batch.append(event)

        if len(batch) >= 500:
            Event.objects.bulk_update(batch, ['rank_score'], batch_size=500)
            updated += len(batch)
            batch = []

    if batch:
        Event.objects.bulk_update(batch, ['rank_score'], batch_size=500)
        updated += len(batch)

    logger.info("Rank scores ricalcolati: %d/%d aggiornati", updated, total)
    return {'total': total, 'updated': updated}


@shared_task(bind=True, max_retries=3, default_retry_delay=10, acks_late=True)
def process_bulk_events(
    self,
    events_data: list[dict],
    spider_name: str = 'unknown',
) -> dict[str, object]:
    """
    Processa un batch di staging events in modo asincrono.

    1. Valida ogni item con EventScrapingSerializer
    2. Usa bulk_create per inserire tutti gli item validi (1 query DB)
    3. Retry automatico su OperationalError (max 3 tentativi)
    4. Fallback a save singoli se bulk_create fallisce
    """
    from .serializers import EventScrapingSerializer
    from .models import Event

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
        serializer = EventScrapingSerializer(data=data)
        if serializer.is_valid():
            valid_instances.append(Event(**serializer.validated_data))
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
        created = Event.objects.bulk_create(valid_instances)
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

    # Invalida cache API external dopo inserimento
    if created_count > 0:
        from .views import _invalidate_external_cache
        _invalidate_external_cache()

    return {
        'spider_name': spider_name,
        'created_count': created_count,
        'failed_count': len(failed_events),
        'failed_events': failed_events,
    }
