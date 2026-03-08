# -*- coding: utf-8 -*-
"""
Inizializzazione OpenTelemetry per lo scraping service.

- Attiva RequestsInstrumentor per propagare automaticamente il trace context
  (header traceparent) nelle richieste HTTP verso il backoffice.
- Se TRACEPARENT è presente come env var (iniettato da Airflow DAG),
  lo usa come parent context per collegare lo spider al trace del DAG.
"""

import os
import logging

logger = logging.getLogger(__name__)

# Tracer globale — no-op se OTel è disabilitato
tracer = None

# Parent context ereditato da Airflow (se presente)
airflow_context = None


def _extract_parent_context():
    """Estrae il parent context da TRACEPARENT env var (W3C Trace Context)."""
    traceparent = os.getenv("TRACEPARENT")
    if not traceparent:
        return None

    try:
        from opentelemetry.propagate import extract

        carrier = {"traceparent": traceparent}
        tracestate = os.getenv("TRACESTATE")
        if tracestate:
            carrier["tracestate"] = tracestate

        ctx = extract(carrier)
        logger.info("Parent context estratto da TRACEPARENT=%s", traceparent)
        return ctx
    except Exception as e:
        logger.warning("Impossibile estrarre parent context da TRACEPARENT: %s", e)
        return None


def _init_otel():
    """Inizializza OTel se OTEL_ENABLED=true, restituisce il tracer."""
    global airflow_context
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

        # Estrai parent context da Airflow (se presente)
        airflow_context = _extract_parent_context()

        logger.info("OpenTelemetry inizializzato: servizio=%s, endpoint=%s", service_name, otlp_endpoint)
        return trace.get_tracer(__name__)

    except ImportError as e:
        logger.warning("OpenTelemetry non disponibile: %s", e)
        return trace.get_tracer(__name__)
    except Exception as e:
        logger.error("Errore inizializzazione OpenTelemetry: %s", e)
        return trace.get_tracer(__name__)


tracer = _init_otel()
