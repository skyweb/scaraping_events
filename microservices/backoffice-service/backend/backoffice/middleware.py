"""
Middleware personalizzati:
- ApiVersionHeaderMiddleware: aggiunge X-API-Version alle risposte API
- AdminRequestLoggingMiddleware: logga richieste all'area admin
"""

import logging
import time

from django.conf import settings

logger = logging.getLogger("admin.requests")


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
