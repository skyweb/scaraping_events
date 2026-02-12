"""
Inizializzazione OpenTelemetry per il backoffice.
Attiva auto-instrumentazione per Django, Psycopg2, Celery e Redis.
Controllato dalla variabile d'ambiente OTEL_ENABLED.
"""

import os
import logging

logger = logging.getLogger(__name__)


def init_otel():
    """Inizializza OpenTelemetry se OTEL_ENABLED=true."""
    if os.environ.get("OTEL_ENABLED", "false").lower() != "true":
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        # Risorsa con nome servizio (da env o default)
        service_name = os.environ.get("OTEL_SERVICE_NAME", "backoffice-django")
        resource = Resource.create({"service.name": service_name})

        # Provider e exporter
        provider = TracerProvider(resource=resource)
        otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        # Auto-instrumentazione Django — solo richieste api/external
        from opentelemetry.instrumentation.django import DjangoInstrumentor
        DjangoInstrumentor().instrument(
            excluded_urls="admin,docs,ckeditor5,assets,static,media,api/schema,api/internal,favicon,health,metrics",
        )

        # Auto-instrumentazione Psycopg2 (query SQL)
        # skip_dep_check=True perché usiamo psycopg2-binary invece di psycopg2
        from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
        Psycopg2Instrumentor().instrument(enable_commenter=True, skip_dep_check=True)

        # Auto-instrumentazione Celery (task spans)
        from opentelemetry.instrumentation.celery import CeleryInstrumentor
        CeleryInstrumentor().instrument()

        # Auto-instrumentazione Redis (operazioni broker)
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        RedisInstrumentor().instrument()

        # Log correlation: inietta otelTraceID, otelSpanID, otelServiceName nei log record
        from opentelemetry.instrumentation.logging import LoggingInstrumentor
        LoggingInstrumentor().instrument(set_logging_format=True)

        logger.info("OpenTelemetry inizializzato: servizio=%s, endpoint=%s", service_name, otlp_endpoint)

    except ImportError as e:
        logger.warning("OpenTelemetry non disponibile, instrumentazione disattivata: %s", e)
    except Exception as e:
        logger.error("Errore durante inizializzazione OpenTelemetry: %s", e)
