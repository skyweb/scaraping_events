"""
API per trasformazione eventi in Schema.org/Event tramite AI (Gemini/Groq).

Autenticazione: SessionAuth (admin) o JWT Keycloak.
"""

import json
import logging
from pathlib import Path

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ai_transform.gemini import (
    AVAILABLE_MODELS,
    DEFAULT_THINKING,
    MODEL_PROVIDERS,
    RateLimitError,
    check_quota,
    get_provider,
    transform_batch,
    transform_event,
)

logger = logging.getLogger(__name__)


def _validate_model(model: str) -> Response | None:
    """Valida il modello e ritorna errore se non supportato."""
    if model not in AVAILABLE_MODELS:
        return Response({
            "error": f"Modello '{model}' non supportato",
            "available_models": AVAILABLE_MODELS,
        }, status=400)
    return None


def _models_info() -> dict:
    """Info sui modelli e parametri disponibili."""
    by_provider: dict[str, list[str]] = {}
    for model, provider in MODEL_PROVIDERS.items():
        by_provider.setdefault(provider, []).append(model)

    return {
        "message": "Specificare il parametro 'model' per avviare la trasformazione.",
        "params": {
            "model": {"required": True, "type": "string", "values": AVAILABLE_MODELS},
            "thinking": {
                "required": False,
                "type": "boolean",
                "default": DEFAULT_THINKING,
                "note": "Solo per modelli Gemini. Attiva ragionamento interno (più costoso).",
            },
            "limit": {
                "required": False,
                "type": "integer",
                "default": 0,
                "note": "Solo per /file/. Limita il numero di eventi da trasformare (0 = tutti).",
            },
        },
        "providers": by_provider,
        "quota": check_quota(),
    }


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def transform_file_view(request):
    """
    Trasforma eventi da un file JSON locale in formato Schema.org/Event.

    POST /api/ai-transform/file/

    Senza 'model': ritorna parametri disponibili e quota rimanente.
    Con 'model': esegue la trasformazione.
    """
    model = request.data.get("model")
    if not model:
        return Response(_models_info())

    if err := _validate_model(model):
        return err

    file_path = request.data.get("file_path")
    if not file_path:
        return Response({"error": "Campo 'file_path' obbligatorio"}, status=400)

    thinking: bool = request.data.get("thinking", DEFAULT_THINKING)
    limit: int = request.data.get("limit", 0)

    # Leggi il file
    path = Path(file_path)
    if not path.is_file():
        return Response({"error": f"File non trovato: {file_path}"}, status=404)

    try:
        with open(path, encoding="utf-8") as f:
            batch_data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return Response({"error": f"Errore lettura file: {e}"}, status=400)

    events = batch_data.get("events", [])
    if not events:
        return Response({"error": "Nessun evento trovato nel file"}, status=400)

    total = len(events)
    if limit > 0:
        events = events[:limit]

    try:
        results, errors = transform_batch(events, model, thinking)
    except ValueError as e:
        return Response({"error": str(e)}, status=500)

    return Response({
        "model": model,
        "provider": get_provider(model),
        "thinking": thinking,
        "source_file": str(path),
        "total_events": total,
        "processed": len(results),
        "errors_count": len(errors),
        "events": results,
        "errors": errors,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def transform_single_view(request):
    """
    Trasforma un singolo evento inline in formato Schema.org/Event.

    POST /api/ai-transform/event/

    Senza 'model': ritorna parametri disponibili e quota rimanente.
    Con 'model': esegue la trasformazione.
    """
    model = request.data.get("model")
    if not model:
        return Response(_models_info())

    if err := _validate_model(model):
        return err

    event = request.data.get("event")
    if not event:
        return Response({"error": "Campo 'event' obbligatorio"}, status=400)

    thinking: bool = request.data.get("thinking", DEFAULT_THINKING)

    try:
        result = transform_event(event, model, thinking)
        return Response({
            "model": model,
            "provider": get_provider(model),
            "thinking": thinking,
            "event": result,
        })
    except RateLimitError as e:
        return Response({"error": str(e)}, status=429)
    except ValueError as e:
        return Response({"error": str(e)}, status=500)
    except Exception as e:
        logger.exception("Errore trasformazione evento")
        return Response({"error": str(e)}, status=500)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def models_view(request):
    """
    Lista modelli disponibili, parametri e quota rimanente.

    GET /api/ai-transform/models/
    """
    return Response(_models_info())
