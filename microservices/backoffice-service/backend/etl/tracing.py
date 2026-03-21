"""
Utility per il tracing distribuito — salva eventi chiave nel DB
per consultazione da Django admin senza bisogno di Jaeger.
"""

import logging
import os

from opentelemetry import trace

logger = logging.getLogger(__name__)


def get_trace_context() -> tuple[str | None, str | None, str | None]:
    """Estrae trace_id e span_id dallo span OTel corrente."""
    span = trace.get_current_span()
    ctx = span.get_span_context()

    if not ctx or not ctx.is_valid:
        return None, None, None

    trace_id = format(ctx.trace_id, '032x')
    span_id = format(ctx.span_id, '016x')

    # Parent span (se disponibile)
    parent_span_id = None
    if hasattr(span, 'parent') and span.parent:
        parent_span_id = format(span.parent.span_id, '016x')

    return trace_id, span_id, parent_span_id


def log_trace_event(
    operation: str,
    message: str | None = None,
    level: str = 'info',
    metadata: dict | None = None,
    service: str | None = None,
) -> object | None:
    """Registra un evento di trace nel DB.

    Args:
        operation: Nome dell'operazione (es. 'bulk.received', 'event.validation_failed')
        message: Messaggio descrittivo o errore
        level: 'info', 'warning', 'error'
        metadata: Dict con dati strutturati (spider, uuid, conteggi, ecc.)
        service: Nome servizio (default da OTEL_SERVICE_NAME)
    """
    trace_id, span_id, parent_span_id = get_trace_context()

    if not trace_id:
        logger.debug("Nessun trace context attivo, skip log_trace_event per %s", operation)
        return None

    if service is None:
        service = os.environ.get('OTEL_SERVICE_NAME', 'backoffice-django')

    try:
        from etl.models import TraceLog
        return TraceLog.objects.create(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            service=service,
            operation=operation,
            level=level,
            message=message,
            metadata=metadata,
        )
    except Exception as e:
        logger.warning("Impossibile salvare trace event: %s", e)
        return None
