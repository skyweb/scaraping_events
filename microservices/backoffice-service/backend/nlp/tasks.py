"""
Task Celery per analisi NLP post-ingestion degli staging events.
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=1, default_retry_delay=30)
def nlp_analyze_events(self, source: str = None, force: bool = False, limit: int = 0):
    """
    Analizza staging events con spaCy NLP ed estrae entità strutturate.
    I risultati vengono salvati in raw_data.nlp.

    Args:
        source: filtra per spider name (None = tutti)
        force: ri-analizza anche eventi già processati
        limit: numero massimo di eventi (0 = tutti)
    """
    from events.models import StagingEvent
    from nlp.extractor import analyze_staging_event

    qs = StagingEvent.objects.filter(description__isnull=False).exclude(description="")

    if source:
        qs = qs.filter(source=source)

    if not force:
        qs = qs.exclude(raw_data__has_key="nlp")

    qs = qs.order_by("-created_at")

    if limit > 0:
        qs = qs[:limit]

    total = qs.count()
    logger.info(f"NLP: analisi di {total} eventi (source={source}, force={force})")

    processed = 0
    enriched = 0
    errors = 0

    for event in qs.iterator():
        try:
            entities = analyze_staging_event(event)
            if entities:
                raw = event.raw_data or {}
                raw["nlp"] = entities
                StagingEvent.objects.filter(pk=event.pk).update(raw_data=raw)
                enriched += 1
            processed += 1
        except Exception as e:
            errors += 1
            logger.warning(f"NLP errore [{event.pk}]: {e}")

    result = {
        "source": source,
        "total": total,
        "processed": processed,
        "enriched": enriched,
        "errors": errors,
    }
    logger.info(f"NLP completato: {result}")
    return result
