# -*- coding: utf-8 -*-
"""
Inizializzazione OpenTelemetry per lo scraping service.
Attiva RequestsInstrumentor per propagare automaticamente il trace context
(header traceparent) nelle richieste HTTP verso il backoffice.
"""

import os
import logging

logger = logging.getLogger(__name__)

# Tracer globale — no-op se OTel è disabilitato
tracer = None


def _init_otel():
    """Inizializza OTel se OTEL_ENABLED=true, restituisce il tracer."""
    from opentelemetry import trace

    if os.getenv("OTEL_ENABLED", "false").lower() != "true":
        return trace.get_tracer(__name__)

    try:
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        service_name = os.getenv("OTEL_SERVICE_NAME", "scraping-service")
        resource = Resource.create({"service.name": service_name})

        provider = TracerProvider(resource=resource)
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        # Auto-instrumentazione requests: inietta header traceparent in ogni richiesta HTTP
        RequestsInstrumentor().instrument()

        logger.info("OpenTelemetry inizializzato: servizio=%s, endpoint=%s", service_name, otlp_endpoint)
        return trace.get_tracer(__name__)

    except ImportError as e:
        logger.warning("OpenTelemetry non disponibile: %s", e)
        return trace.get_tracer(__name__)
    except Exception as e:
        logger.error("Errore inizializzazione OpenTelemetry: %s", e)
        return trace.get_tracer(__name__)


tracer = _init_otel()
