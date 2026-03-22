"""
Middleware personalizzati:
- ApiVersionHeaderMiddleware: aggiunge X-API-Version alle risposte API
- AdminRequestLoggingMiddleware: logga richieste all'area admin
- KeycloakAdminMiddleware: SSO trasparente per /admin/ via APISIX + Keycloak
"""

import base64
import json
import logging
import time

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.models import Group, Permission
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse

logger = logging.getLogger("admin.requests")


sso_logger = logging.getLogger("admin.sso")


class KeycloakAdminMiddleware:
    """
    SSO trasparente per Django Admin via APISIX openid-connect + Keycloak.

    Flusso:
      1. APISIX autentica la richiesta via plugin openid-connect → Keycloak
      2. Keycloak valida la sessione/token e restituisce i claim
      3. APISIX imposta X-Userinfo (JSON) nell'header con i claim OIDC
      4. Questo middleware legge l'email da X-Userinfo, verifica il ruolo
         "web" o "admin", e fa il login automatico

    Attivo solo su /admin/. Le API (/api/) usano JWT diretto.
    Ruoli richiesti: "web" o "admin" (configurato in KEYCLOAK_ADMIN_ALLOWED_ROLES).
    Se l'utente Django non esiste, viene creato automaticamente (auto-provisioning).
    """

    # Ruoli Keycloak che permettono l'accesso al Django Admin
    ALLOWED_ROLES = {"web", "admin"}

    # Permessi Django assegnati al gruppo "Redazione" (ruolo "web")
    # Formato: (app_label, codename)
    REDAZIONE_PERMISSIONS = [
        ("events", "view_event"),
    ]

    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Solo per /admin/, solo se non già autenticato
        if not request.path.startswith("/admin/") or request.user.is_authenticated:
            return self.get_response(request)

        userinfo = self._extract_userinfo(request)
        email = userinfo.get("email", "").strip()
        if not email:
            # Header assente: APISIX non attivo o accesso diretto (es. :8000)
            return self.get_response(request)

        # Verifica ruolo Keycloak dall'header X-Userinfo (JSON dai claim OIDC)
        # I ruoli possono essere in "realm_access.roles" (access token) o "groups" (userinfo mapper)
        roles = userinfo.get("realm_access", {}).get("roles", []) or userinfo.get("groups", [])
        if not (self.ALLOWED_ROLES & set(roles)):
            sso_logger.warning(
                "SSO accesso negato: ruolo mancante",
                extra={"email": email, "roles": roles, "required": list(self.ALLOWED_ROLES)},
            )
            return TemplateResponse(
                request,
                "admin/sso_access_denied.html",
                {"email": email, "not_staff": False, "missing_role": True},
                status=403,
            ).render()

        User = get_user_model()
        kc_username = userinfo.get("preferred_username", "").strip() or email.split("@")[0]

        # Cerca per preferred_username di Keycloak (attivo o disattivato)
        user = User.objects.filter(username=kc_username).first()
        # Fallback: cerca per email
        if user is None:
            user = User.objects.filter(email=email).first()

        if user is not None:
            # Riattiva se disattivato, assicura is_staff
            changed = False
            if not user.is_active:
                user.is_active = True
                changed = True
            if not user.is_staff:
                user.is_staff = True
                changed = True
            if changed:
                user.save(update_fields=["is_active", "is_staff"])
                sso_logger.info(
                    "SSO riattivazione utente",
                    extra={"email": email, "username": user.username},
                )

        if user is None:
            # Auto-provisioning: crea utente Django da Keycloak
            # Username da preferred_username Keycloak (con fallback suffisso numerico)
            username = self._unique_username(User, kc_username)
            is_superuser = "admin" in set(roles)
            user = User(
                username=username,
                email=email,
                first_name=userinfo.get("given_name", ""),
                last_name=userinfo.get("family_name", ""),
                is_staff=True,
                is_superuser=is_superuser,
            )
            user.set_unusable_password()
            user.save()
            sso_logger.info(
                "SSO auto-provisioning utente",
                extra={"email": email, "username": username, "roles": roles, "is_superuser": is_superuser},
            )

            # Ruolo "web" → gruppo "Redazione" con permessi limitati
            if not is_superuser:
                group = self._get_or_create_redazione_group()
                user.groups.add(group)

        if not user.is_staff:
            return TemplateResponse(
                request,
                "admin/sso_access_denied.html",
                {"email": email, "not_staff": True},
                status=403,
            ).render()

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        sso_logger.info(
            "SSO login via APISIX/Keycloak",
            extra={"email": email, "user": user.get_username(), "roles": roles},
        )
        return self.get_response(request)

    @staticmethod
    def _unique_username(user_model, base: str) -> str:
        """Genera uno username unico: prova 'base', poi 'base-1', 'base-2', ecc."""
        if not user_model.objects.filter(username=base).exists():
            return base
        n = 1
        while user_model.objects.filter(username=f"{base}-{n}").exists():
            n += 1
        return f"{base}-{n}"

    @classmethod
    def _get_or_create_redazione_group(cls) -> Group:
        """Crea il gruppo Redazione con i permessi definiti in REDAZIONE_PERMISSIONS."""
        group, created = Group.objects.get_or_create(name="Redazione")
        if created:
            perms = Permission.objects.filter(
                content_type__app_label__in=[p[0] for p in cls.REDAZIONE_PERMISSIONS],
                codename__in=[p[1] for p in cls.REDAZIONE_PERMISSIONS],
            )
            group.permissions.set(perms)
            sso_logger.info("Gruppo Redazione creato con %d permessi", perms.count())
        return group

    @staticmethod
    def _extract_userinfo(request: HttpRequest) -> dict:
        """Decodifica l'header X-Userinfo (JSON plain da APISIX o base64 legacy)."""
        raw = request.META.get("HTTP_X_USERINFO", "")
        if not raw:
            return {}
        # APISIX invia JSON plain
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            pass
        # Fallback: base64-encoded JSON (oauth2-proxy legacy)
        try:
            return json.loads(base64.b64decode(raw))
        except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
            return {}


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
