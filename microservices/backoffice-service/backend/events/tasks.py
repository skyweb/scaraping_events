import logging

from celery import shared_task
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
    Processa un batch di eventi in modo asincrono e li scrive su MongoDB.

    1. Valida ogni item con EventScrapingSerializer
    2. Scrive su MongoDB (upsert per uuid) — Postgres non viene coinvolto
    3. Retry automatico su errori MongoDB (max 3 tentativi)
    """
    from .serializers import EventScrapingSerializer
    from events.mongo_repository import validated_data_to_doc, upsert_events

    logger.info("Processing bulk events from spider: %s (%d events)", spider_name, len(events_data))

    span = trace.get_current_span()
    span.set_attribute("bulk.spider", spider_name)
    span.set_attribute("bulk.total_events", len(events_data))

    log_trace_event(
        'celery.processing',
        f'Celery task avviato: {len(events_data)} eventi da {spider_name}',
        service='backoffice-celery-worker',
        metadata={'spider': spider_name, 'events_count': len(events_data), 'task_id': self.request.id},
    )

    valid_docs = []
    failed_events = []

    # 1. Valida ogni item e costruisce il documento MongoDB
    for idx, data in enumerate(events_data):
        serializer = EventScrapingSerializer(data=data)
        if serializer.is_valid():
            valid_docs.append(validated_data_to_doc(serializer.validated_data, spider_name))
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
                data.get("uuid", ""), idx, str(serializer.errors)[:200],
            )

    if not valid_docs:
        span.set_attribute("bulk.created_count", 0)
        span.set_attribute("bulk.failed_count", len(failed_events))
        span.set_status(StatusCode.ERROR, f"Tutti i {len(failed_events)} eventi falliti in validazione")
        return {
            'spider_name': spider_name,
            'created_count': 0,
            'failed_count': len(failed_events),
            'failed_events': failed_events,
        }

    # 2. Scrivi su MongoDB
    try:
        created_count = upsert_events(valid_docs)
        for doc in valid_docs:
            span.add_event("event.created", attributes={
                "event.uuid": doc["uuid"],
                "event.title": str(doc.get("title", ""))[:80],
            })
            logger.info("Evento scritto su MongoDB: uuid=%s title=%s", doc["uuid"], str(doc.get("title", ""))[:80])
    except Exception as exc:
        span.set_status(StatusCode.ERROR, f"MongoDB write error: {exc}")
        span.add_event("bulk.retry", attributes={
            "retry.attempt": self.request.retries + 1,
            "retry.error": str(exc)[:200],
        })
        logger.warning("MongoDB upsert fallito, retry: %s", exc)
        raise self.retry(exc=exc)

    span.set_attribute("bulk.created_count", created_count)
    span.set_attribute("bulk.failed_count", len(failed_events))
    span.set_attribute("bulk.validated_count", len(valid_docs))

    if failed_events:
        span.set_status(StatusCode.ERROR, f"{len(failed_events)} eventi falliti su {len(events_data)}")
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
            f'{created_count} eventi scritti su MongoDB da {spider_name}',
            service='backoffice-celery-worker',
            metadata={'spider': spider_name, 'task_id': self.request.id, 'created_count': created_count},
        )

    if created_count > 0:
        from .views import _invalidate_external_cache
        _invalidate_external_cache()

    return {
        'spider_name': spider_name,
        'created_count': created_count,
        'failed_count': len(failed_events),
        'failed_events': failed_events,
    }
