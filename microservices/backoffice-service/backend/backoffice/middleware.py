"""
Middleware personalizzati:
- ApiVersionHeaderMiddleware: aggiunge X-API-Version alle risposte API
- AdminRequestLoggingMiddleware: logga richieste all'area admin
- KeycloakAdminMiddleware: SSO trasparente per /admin/ via APISIX + Keycloak
"""

import logging
import time

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse

logger = logging.getLogger("admin.requests")


sso_logger = logging.getLogger("admin.sso")


class KeycloakAdminMiddleware:
    """
    SSO trasparente per Django Admin via APISIX + Keycloak.

    Flusso:
      1. APISIX autentica la richiesta via plugin openid-connect → Keycloak
      2. Keycloak valida la sessione/token e restituisce i claim
      3. APISIX imposta X-Auth-Request-Email nell'header della richiesta
      4. Questo middleware legge l'email e fa il login automatico

    Attivo solo su /admin/. Le API (/api/) usano JWT diretto.
    Non crea utenti automaticamente: l'utente Django deve esistere con la stessa email
    e avere is_staff=True. In caso contrario restituisce 403 con istruzioni.
    """

    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Solo per /admin/, solo se non già autenticato
        if not request.path.startswith("/admin/") or request.user.is_authenticated:
            return self.get_response(request)

        email = request.META.get("HTTP_X_AUTH_REQUEST_EMAIL", "").strip()
        if not email:
            # Header assente: oauth2-proxy non attivo o accesso diretto (es. :8000)
            return self.get_response(request)

        User = get_user_model()
        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            return TemplateResponse(
                request,
                "admin/oauth2_proxy_denied.html",
                {"email": email, "not_staff": False},
                status=403,
            ).render()

        if not user.is_staff:
            return TemplateResponse(
                request,
                "admin/oauth2_proxy_denied.html",
                {"email": email, "not_staff": True},
                status=403,
            ).render()

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        sso_logger.info(
            "SSO login via oauth2-proxy",
            extra={"email": email, "user": user.get_username()},
        )
        return self.get_response(request)


class ApiVersionHeaderMiddleware:
    """Aggiunge header X-API-Version a tutte le risposte /api/."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.default_version = getattr(settings, 'API_VERSION', 'v1')

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            version = getattr(request, 'version', None) or self.default_version
            response["X-API-Version"] = version
        return response


class AdminRequestLoggingMiddleware:
    """Logga le richieste HTTP verso /admin/ con durata e status code."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/admin/"):
            return self.get_response(request)

        start = time.monotonic()
        response = self.get_response(request)
        duration_ms = round((time.monotonic() - start) * 1000)

        user = request.user.get_username() if hasattr(request, "user") and request.user.is_authenticated else "anonymous"
        status_code = response.status_code

        extra = {
            "path": request.path,
            "method": request.method,
            "status_code": status_code,
            "user": user,
            "duration_ms": duration_ms,
        }

        if status_code >= 500:
            logger.error("Admin %s %s -> %s (%dms)", request.method, request.path, status_code, duration_ms, extra=extra)
        elif status_code >= 400:
            logger.warning("Admin %s %s -> %s (%dms)", request.method, request.path, status_code, duration_ms, extra=extra)
        else:
            logger.info("Admin %s %s -> %s (%dms)", request.method, request.path, status_code, duration_ms, extra=extra)

        return response

    def process_exception(self, request, exception):
        """Logga eccezioni non gestite nelle view admin."""
        if request.path.startswith("/admin/"):
            user = request.user.get_username() if hasattr(request, "user") and request.user.is_authenticated else "anonymous"
            logger.error(
                "Admin exception: %s %s - %s: %s",
                request.method,
                request.path,
                type(exception).__name__,
                exception,
                extra={
                    "path": request.path,
                    "method": request.method,
                    "user": user,
                    "exception_type": type(exception).__name__,
                },
                exc_info=True,
            )
        return None
