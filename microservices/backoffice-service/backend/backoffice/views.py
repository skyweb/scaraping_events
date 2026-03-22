import os

from django.conf import settings
from django.contrib.auth import logout as auth_logout
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render


def admin_sso_logout(request):
    """
    Logout unificato SSO: cancella la sessione Django, poi delega ad APISIX
    il logout OIDC (cancella cookie sessione APISIX + redirect a Keycloak logout).
    Il path /admin/sso-logout è intercettato dal plugin openid-connect di APISIX.
    """
    auth_logout(request)
    return redirect("/admin/sso-logout")


def permission_denied_view(request, exception):
    return render(request, '403.html', status=403)


def _get_git_commit():
    """Legge il commit hash da GIT_COMMIT env o .git/HEAD."""
    commit = os.environ.get("GIT_COMMIT", "")
    if commit:
        return commit[:8]
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--short=8", "HEAD"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


_GIT_COMMIT = _get_git_commit()

API_VERSION_STRING = "1.0.0"


def api_version_view(request):
    """Endpoint pubblico — semantic version + commit hash (se disponibile)."""
    data = {
        "version": API_VERSION_STRING,
        "api_versions": settings.API_ALLOWED_VERSIONS,
        "default_version": settings.API_VERSION,
    }
    if _GIT_COMMIT:
        data["commit"] = _GIT_COMMIT
    return JsonResponse(data)


def openapi_download_view(request):
    """Scarica lo schema OpenAPI come file JSON (per import Postman)."""
    from drf_spectacular.generators import SchemaGenerator
    generator = SchemaGenerator(api_version=settings.API_VERSION)
    schema = generator.get_schema(public=True)

    import json
    content = json.dumps(schema, indent=2, ensure_ascii=False)

    response = HttpResponse(content, content_type="application/json")
    response["Content-Disposition"] = 'attachment; filename="today-events-api.json"'
    return response


# --- DRF view per inclusione nello schema OpenAPI ---
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiExample


@extend_schema(
    summary="Versione API",
    description="Restituisce la versione semantica dell'API",
    tags=["Sistema"],
    responses={
        200: {
            "type": "object",
            "properties": {
                "version": {"type": "string", "example": "1.0.0"},
                "commit": {"type": "string", "example": "83bb319a"},
                "api_versions": {"type": "array", "items": {"type": "string"}, "example": ["v1"]},
                "default_version": {"type": "string", "example": "v1"},
            },
        },
    },
    examples=[
        OpenApiExample(
            "Con commit hash",
            value={"version": "1.0.0", "commit": "83bb319a", "api_versions": ["v1"], "default_version": "v1"},
            response_only=True,
        ),
        OpenApiExample(
            "Senza commit (non compilato da git)",
            value={"version": "1.0.0", "api_versions": ["v1"], "default_version": "v1"},
            response_only=True,
        ),
    ],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def api_version_drf_view(request):
    """Endpoint pubblico — semantic version + commit hash (se disponibile)."""
    data = {
        "version": API_VERSION_STRING,
        "api_versions": settings.API_ALLOWED_VERSIONS,
        "default_version": settings.API_VERSION,
    }
    if _GIT_COMMIT:
        data["commit"] = _GIT_COMMIT
    return Response(data)


def services_dashboard(request):
    """Dashboard servizi — pagina home con link a tutti i servizi dello stack."""
    return render(request, 'dashboard/services.html')


def _scalar_html(title: str, schema_url: str) -> str:
    """Genera HTML per Scalar API Reference con schema URL configurabile."""
    return f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
</head>
<body>
    <script id="api-reference" data-url="{schema_url}"></script>
    <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
</body>
</html>"""


def scalar_view(request):
    """Scalar API Reference UI — schema interno (tutti gli endpoint)."""
    return HttpResponse(_scalar_html("Events Backoffice API - Internal", "/docs/schema/"), content_type="text/html")


def scalar_public_view(request):
    """Scalar API Reference UI — schema pubblico (/api/v1/events/, /version/)."""
    return HttpResponse(_scalar_html("Events API - Public", "/docs/public/schema/"), content_type="text/html")
