"""
Client multi-provider per trasformazione eventi in Schema.org/Event.

Provider supportati:
- Gemini (Google): gemini-2.5-flash-lite, gemini-2.5-flash, gemini-2.5-pro, gemma-3-*
- Groq: llama-3.3-70b-versatile, llama-3.1-8b-instant, qwen/qwen3-32b

Default: gemini-2.5-flash-lite (Gemini)
Tracing: OpenTelemetry span per ogni chiamata AI.
"""

import json
import logging
import time
from datetime import date

import requests
from django.conf import settings
from django.core.cache import cache
from opentelemetry import trace

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("ai_transform")

# --- Configurazione provider e modelli ---

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

DEFAULT_MODEL = "gemini-2.5-flash-lite"
DEFAULT_THINKING = False

# Mappa modello → provider
MODEL_PROVIDERS: dict[str, str] = {
    # Gemini
    "gemini-2.5-flash-lite": "gemini",
    "gemini-2.5-flash": "gemini",
    "gemini-2.5-pro": "gemini",
    "gemma-3-4b-it": "gemini",
    "gemma-3-12b-it": "gemini",
    "gemma-3-27b-it": "gemini",
    # Groq
    "llama-3.3-70b-versatile": "groq",
    "llama-3.1-8b-instant": "groq",
    "qwen/qwen3-32b": "groq",
}

AVAILABLE_MODELS = list(MODEL_PROVIDERS.keys())

SCHEMA_ORG_PROMPT = """\
Sei un esperto di dati strutturati Schema.org.
Ti verrà dato un evento in formato JSON grezzo (scraping).
Trasformalo in un oggetto JSON valido che rispetti lo schema https://schema.org/Event.

Regole:
1. Usa SOLO proprietà definite in Schema.org/Event
2. Estrai date e orari dall'HTML in date_display se date_start/date_end sono vuoti
3. Mappa city_name → location.address.addressLocality
4. Mappa location_name → location.name
5. Estrai il prezzo da section.events_dati o section.info_e_costi (offers.price, priceCurrency EUR)
6. Estrai la rassegna come superEvent.name se presente
7. image_url → image
8. Estrai il cast da section.casting:
   - Attori/interpreti → performer (array di Person con name e roleName)
   - Regista → director (Person con name)
   - Compagnia/produzione → organizer (Organization con name)
9. Estrai contatti da section.info_e_contatti:
   - Telefono → organizer.telephone
   - Email → organizer.email
10. Estrai orari biglietteria da section.info_e_costi → offers.availabilityStarts o offers.description
11. section.website → url (sito ufficiale dell'evento)
12. location_address → location.address.streetAddress
13. Restituisci SOLO il JSON, senza markdown, senza spiegazioni
14. Se un campo non ha dati sufficienti, omettilo (non inventare)
15. Le date devono essere in formato ISO 8601
16. Pulisci l'HTML dalla description, restituisci solo testo pulito

Esempio di output atteso:
{
  "@context": "https://schema.org",
  "@type": "Event",
  "name": "Nome Evento",
  "startDate": "2026-01-15T20:30:00",
  "endDate": "2026-01-15T22:00:00",
  "location": {
    "@type": "Place",
    "name": "Teatro Comunale",
    "address": {
      "@type": "PostalAddress",
      "addressLocality": "Bari"
    }
  },
  "image": "https://example.com/image.jpg",
  "description": "Descrizione evento in testo pulito",
  "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
  "performer": [
    {
      "@type": "Person",
      "name": "Mario Rossi",
      "roleName": "attore"
    }
  ],
  "director": {
    "@type": "Person",
    "name": "Luigi Bianchi"
  },
  "organizer": {
    "@type": "Organization",
    "name": "Compagnia Teatrale XYZ",
    "telephone": "+39 080 1234567",
    "email": "info@example.com"
  },
  "offers": {
    "@type": "Offer",
    "price": "15.00",
    "priceCurrency": "EUR",
    "description": "Biglietteria aperta una settimana prima dello spettacolo"
  },
  "url": "https://www.example.com/evento",
  "superEvent": {
    "@type": "Event",
    "name": "Nome Rassegna"
  }
}
"""


class RateLimitError(Exception):
    """Limite gratuito raggiunto sul provider AI."""

    def __init__(self, provider: str, model: str, retry_after: str = ""):
        self.provider = provider
        self.model = model
        self.retry_after = retry_after
        msg = (
            f"Limite gratuito {provider} raggiunto per il modello '{model}'. "
        )
        if retry_after:
            msg += f"Riprova tra {retry_after}. "
        msg += (
            "Puoi: 1) attendere il reset del limite, "
            "2) usare un modello di un altro provider (es. Groq/Gemini), "
            "3) passare a un piano a pagamento."
        )
        super().__init__(msg)


# --- OTel helpers ---

def _set_span_base(span: trace.Span, provider: str, model: str) -> None:
    """Imposta attributi base dello span AI."""
    span.set_attribute("ai.provider", provider)
    span.set_attribute("ai.model", model)
    span.set_attribute("ai.system", "ai_transform")


def _set_span_success(
    span: trace.Span,
    duration_ms: float,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
) -> None:
    """Imposta attributi di successo sullo span."""
    span.set_attribute("ai.status", "success")
    span.set_attribute("ai.duration_ms", duration_ms)
    if prompt_tokens:
        span.set_attribute("ai.usage.prompt_tokens", prompt_tokens)
    if completion_tokens:
        span.set_attribute("ai.usage.completion_tokens", completion_tokens)
    if total_tokens:
        span.set_attribute("ai.usage.total_tokens", total_tokens)


def _set_span_error(span: trace.Span, error: str, error_type: str = "error") -> None:
    """Imposta attributi di errore sullo span."""
    span.set_attribute("ai.status", error_type)
    span.set_attribute("ai.error", error)
    span.set_status(trace.StatusCode.ERROR, error)


# --- Gemini ---

def _call_gemini(
    event: dict,
    api_key: str,
    model: str,
    thinking: bool,
) -> tuple[dict, dict]:
    """Chiama l'API Gemini e restituisce (JSON Schema.org, quota_info)."""
    with tracer.start_as_current_span("ai.transform_event") as span:
        _set_span_base(span, "gemini", model)
        span.set_attribute("ai.thinking", thinking)
        start = time.monotonic()

        url = f"{GEMINI_API_URL}/{model}:generateContent?key={api_key}"
        payload: dict = {
            "contents": [
                {
                    "parts": [
                        {"text": SCHEMA_ORG_PROMPT},
                        {"text": f"Evento da trasformare:\n{json.dumps(event, ensure_ascii=False)}"},
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1,
                "thinkingConfig": {"thinkingBudget": -1 if thinking else 0},
            },
        }

        try:
            response = requests.post(url, json=payload, timeout=30)
            duration_ms = (time.monotonic() - start) * 1000
            span.set_attribute("http.status_code", response.status_code)

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "qualche minuto")
                _set_span_error(span, f"rate_limit (retry: {retry_after})", "rate_limit")
                raise RateLimitError("Gemini", model, retry_after)

            response.raise_for_status()
            result = response.json()

            # Token usage
            usage = result.get("usageMetadata", {})
            _set_span_success(
                span,
                duration_ms,
                prompt_tokens=usage.get("promptTokenCount", 0),
                completion_tokens=usage.get("candidatesTokenCount", 0),
                total_tokens=usage.get("totalTokenCount", 0),
            )
            if usage.get("thoughtsTokenCount"):
                span.set_attribute("ai.usage.thinking_tokens", usage["thoughtsTokenCount"])

            # Quota info da headers (Gemini non espone remaining, ma fornisce RPM/RPD)
            quota_info = _extract_gemini_quota(model)

            parts = result["candidates"][0]["content"]["parts"]
            text = parts[-1]["text"]
            return json.loads(text), quota_info

        except RateLimitError:
            raise
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            _set_span_error(span, str(e))
            span.set_attribute("ai.duration_ms", duration_ms)
            raise


# Limiti free tier noti per modello Gemini (req/giorno)
GEMINI_FREE_LIMITS: dict[str, dict] = {
    "gemini-2.5-flash-lite": {"rpm": 30, "rpd": 1500},
    "gemini-2.5-flash": {"rpm": 10, "rpd": 500},
    "gemini-2.5-pro": {"rpm": 5, "rpd": 25},
    "gemma-3-4b-it": {"rpm": 30, "rpd": 1500},
    "gemma-3-12b-it": {"rpm": 30, "rpd": 1500},
    "gemma-3-27b-it": {"rpm": 15, "rpd": 500},
}


def _gemini_usage_cache_key(model: str) -> str:
    """Chiave cache per contatore giornaliero Gemini: ai:gemini:{model}:YYYY-MM-DD."""
    return f"ai:gemini:{model}:{date.today().isoformat()}"


def _increment_gemini_usage(model: str) -> int:
    """Incrementa il contatore giornaliero e restituisce il nuovo valore."""
    key = _gemini_usage_cache_key(model)
    try:
        count = cache.get(key, 0) + 1
        # TTL 25 ore — copre il giorno corrente con margine
        cache.set(key, count, timeout=90000)
        return count
    except Exception:
        return 0


def _get_gemini_usage(model: str) -> int:
    """Restituisce il contatore giornaliero corrente."""
    try:
        return cache.get(_gemini_usage_cache_key(model), 0)
    except Exception:
        return 0


def _extract_gemini_quota(model: str) -> dict:
    """Restituisce quota Gemini con residuo calcolato dal contatore giornaliero."""
    limits = GEMINI_FREE_LIMITS.get(model, {})
    rpd = limits.get("rpd", 0)
    used = _increment_gemini_usage(model)
    remaining = max(0, rpd - used)

    return {
        "provider": "gemini",
        "remaining_requests": remaining,
        "limit_requests": rpd,
        "used_today": used,
        "rpm": limits.get("rpm"),
    }


# --- Groq ---

def _call_groq(
    event: dict,
    api_key: str,
    model: str,
) -> tuple[dict, dict]:
    """Chiama l'API Groq (compatibile OpenAI) e restituisce (JSON Schema.org, quota_info)."""
    with tracer.start_as_current_span("ai.transform_event") as span:
        _set_span_base(span, "groq", model)
        start = time.monotonic()

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SCHEMA_ORG_PROMPT},
                {
                    "role": "user",
                    "content": f"Evento da trasformare:\n{json.dumps(event, ensure_ascii=False)}",
                },
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        try:
            response = requests.post(
                GROQ_API_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            duration_ms = (time.monotonic() - start) * 1000
            span.set_attribute("http.status_code", response.status_code)

            # Groq rate limit headers (presenti anche su 200)
            remaining_req = response.headers.get("x-ratelimit-remaining-requests")
            remaining_tok = response.headers.get("x-ratelimit-remaining-tokens")
            if remaining_req is not None:
                span.set_attribute("ai.quota.remaining_requests", int(remaining_req))
            if remaining_tok is not None:
                span.set_attribute("ai.quota.remaining_tokens", int(remaining_tok))

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "qualche minuto")
                _set_span_error(span, f"rate_limit (retry: {retry_after})", "rate_limit")
                raise RateLimitError("Groq", model, retry_after)

            response.raise_for_status()
            result = response.json()

            # Token usage
            usage = result.get("usage", {})
            _set_span_success(
                span,
                duration_ms,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            )

            # Quota info dai headers Groq
            quota_info = _extract_groq_quota(response.headers)

            text = result["choices"][0]["message"]["content"]
            return json.loads(text), quota_info

        except RateLimitError:
            raise
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            _set_span_error(span, str(e))
            span.set_attribute("ai.duration_ms", duration_ms)
            raise


def _extract_groq_quota(headers: dict) -> dict:
    """Estrae info quota dai response headers Groq."""
    return {
        "provider": "groq",
        "remaining_requests": headers.get("x-ratelimit-remaining-requests"),
        "limit_requests": headers.get("x-ratelimit-limit-requests"),
        "remaining_tokens": headers.get("x-ratelimit-remaining-tokens"),
        "limit_tokens": headers.get("x-ratelimit-limit-tokens"),
        "reset_requests": headers.get("x-ratelimit-reset-requests"),
        "reset_tokens": headers.get("x-ratelimit-reset-tokens"),
    }


# --- Quota check ---

def _check_gemini_quota(api_key: str) -> dict:
    """Verifica la quota Gemini con una richiesta minimale."""
    url = f"{GEMINI_API_URL}/gemini-2.5-flash-lite:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": "ok"}]}],
        "generationConfig": {"maxOutputTokens": 1},
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 429:
            return {"status": "limit_reached", "message": "Limite gratuito raggiunto"}
        if r.status_code == 200:
            return {"status": "available", "message": "API key valida, quota disponibile"}
        return {"status": "error", "message": f"HTTP {r.status_code}"}
    except requests.RequestException as e:
        return {"status": "error", "message": str(e)}


def _check_groq_quota(api_key: str) -> dict:
    """Verifica la quota Groq con una richiesta minimale. Groq ritorna headers di rate limit."""
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": "ok"}],
        "max_completion_tokens": 5,
    }
    try:
        r = requests.post(
            GROQ_API_URL,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=10,
        )
        if r.status_code == 429:
            retry = r.headers.get("retry-after", "?")
            return {"status": "limit_reached", "message": f"Rate limit raggiunto, riprova tra {retry}s"}
        if r.status_code == 200:
            return {
                "status": "available",
                "remaining_requests": r.headers.get("x-ratelimit-remaining-requests", "?"),
                "remaining_tokens": r.headers.get("x-ratelimit-remaining-tokens", "?"),
                "reset": r.headers.get("x-ratelimit-reset", "?"),
            }
        return {"status": "error", "message": f"HTTP {r.status_code}"}
    except requests.RequestException as e:
        return {"status": "error", "message": str(e)}


def check_quota() -> dict[str, dict]:
    """Verifica la quota disponibile per ogni provider configurato."""
    result: dict[str, dict] = {}

    gemini_key = getattr(settings, "GEMINI_API_KEY", "")
    if gemini_key:
        result["gemini"] = _check_gemini_quota(gemini_key)
    else:
        result["gemini"] = {"status": "not_configured", "message": "GEMINI_API_KEY mancante"}

    groq_key = getattr(settings, "GROQ_API_KEY", "")
    if groq_key:
        result["groq"] = _check_groq_quota(groq_key)
    else:
        result["groq"] = {"status": "not_configured", "message": "GROQ_API_KEY mancante"}

    return result


# --- API pubblica ---

def get_provider(model: str) -> str:
    """Restituisce il provider per un dato modello."""
    return MODEL_PROVIDERS.get(model, "gemini")


def transform_event(
    event: dict,
    model: str = DEFAULT_MODEL,
    thinking: bool = DEFAULT_THINKING,
) -> tuple[dict, dict]:
    """
    Trasforma un singolo evento in formato Schema.org/Event.

    Seleziona automaticamente il provider (Gemini/Groq) in base al modello.
    Restituisce (schema_org_dict, quota_info).
    """
    provider = get_provider(model)

    if provider == "groq":
        api_key = getattr(settings, "GROQ_API_KEY", "")
        if not api_key:
            raise ValueError("GROQ_API_KEY non configurata in settings")
        return _call_groq(event, api_key, model)

    # Default: Gemini
    api_key = getattr(settings, "GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY non configurata in settings")
    return _call_gemini(event, api_key, model, thinking)


def transform_text(
    prompt: str,
    text: str,
    model: str = DEFAULT_MODEL,
    thinking: bool = DEFAULT_THINKING,
) -> tuple[str, dict]:
    """
    Chiamata AI generica: invia prompt + testo e restituisce (risposta, quota_info).

    Utile per estrazioni, riassunti, riformattazioni di testo libero.
    """
    provider = get_provider(model)

    if provider == "groq":
        api_key = getattr(settings, "GROQ_API_KEY", "")
        if not api_key:
            raise ValueError("GROQ_API_KEY non configurata in settings")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            "temperature": 0.1,
        }
        response = requests.post(
            GROQ_API_URL,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=30,
        )
        if response.status_code == 429:
            raise RateLimitError("Groq", model, response.headers.get("Retry-After", "qualche minuto"))
        response.raise_for_status()
        quota_info = _extract_groq_quota(response.headers)
        return response.json()["choices"][0]["message"]["content"], quota_info

    # Default: Gemini
    api_key = getattr(settings, "GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY non configurata in settings")
    url = f"{GEMINI_API_URL}/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}, {"text": text}]}],
        "generationConfig": {
            "temperature": 0.1,
            "thinkingConfig": {"thinkingBudget": -1 if thinking else 0},
        },
    }
    response = requests.post(url, json=payload, timeout=30)
    if response.status_code == 429:
        raise RateLimitError("Gemini", model, response.headers.get("Retry-After", "qualche minuto"))
    response.raise_for_status()
    quota_info = _extract_gemini_quota(model)
    result = response.json()
    parts = result["candidates"][0]["content"]["parts"]
    return parts[-1]["text"], quota_info


def transform_batch(
    events: list[dict],
    model: str = DEFAULT_MODEL,
    thinking: bool = DEFAULT_THINKING,
) -> tuple[list[dict], list[dict]]:
    """
    Trasforma una lista di eventi in formato Schema.org/Event.

    Crea uno span padre per l'intero batch con statistiche aggregate.
    """
    results: list[dict] = []
    errors: list[dict] = []

    with tracer.start_as_current_span("ai.transform_batch") as batch_span:
        _set_span_base(batch_span, get_provider(model), model)
        batch_span.set_attribute("ai.batch.total_events", len(events))

        for i, event in enumerate(events):
            try:
                schema_event, _quota = transform_event(event, model, thinking)
                results.append(schema_event)
                logger.info(f"Evento {i + 1}/{len(events)} trasformato: {event.get('title', 'N/A')}")
            except RateLimitError as e:
                logger.warning(f"Rate limit raggiunto all'evento {i + 1}/{len(events)}: {e}")
                for j in range(i, len(events)):
                    errors.append({
                        "index": j,
                        "title": events[j].get("title", "N/A"),
                        "error": str(e),
                    })
                batch_span.set_attribute("ai.batch.stopped_at", i)
                batch_span.set_attribute("ai.batch.stop_reason", "rate_limit")
                break
            except Exception as e:
                logger.warning(f"Errore evento {i + 1}/{len(events)}: {e}")
                errors.append({
                    "index": i,
                    "title": event.get("title", "N/A"),
                    "error": str(e),
                })

        batch_span.set_attribute("ai.batch.processed", len(results))
        batch_span.set_attribute("ai.batch.errors", len(errors))
        if errors:
            batch_span.set_status(trace.StatusCode.ERROR, f"{len(errors)} errori")

    return results, errors
