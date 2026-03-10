from django.conf import settings
from django.contrib.auth import logout as auth_logout
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render


def admin_sso_logout(request):
    """
    Logout unificato SSO: cancella la sessione Django E la sessione Keycloak.
    Sovrascrive /admin/logout/ prima che venga gestito da admin.site.urls.
    Senza questo, Django cancella la sessione ma il cookie APISIX OIDC rimane
    valido → il middleware ri-autentica l'utente al prossimo accesso.
    """
    auth_logout(request)
    # Redirect all'endpoint logout di Keycloak con post_logout_redirect_uri
    scheme = "https" if request.is_secure() else "http"
    host = request.get_host()  # es. backoffice.127.0.0.1.nip.io
    domain = host.split(".", 1)[1] if "." in host else host  # es. 127.0.0.1.nip.io
    keycloak_url = settings.KEYCLOAK_URL
    realm = settings.KEYCLOAK_REALM
    redirect_uri = f"{scheme}://backoffice.{domain}/admin/"
    logout_url = (
        f"{keycloak_url}/realms/{realm}/protocol/openid-connect/logout"
        f"?post_logout_redirect_uri={redirect_uri}"
        f"&client_id=backoffice-admin"
    )
    return redirect(logout_url)


def permission_denied_view(request, exception):
    return render(request, '403.html', status=403)


def api_version_view(request):
    """Endpoint pubblico che restituisce la versione corrente dell'API."""
    return JsonResponse({
        "version": "1.0.0",
        "api_versions": settings.API_ALLOWED_VERSIONS,
        "default_version": settings.API_VERSION,
    })


def scalar_view(request):
    """Scalar API Reference UI — punta allo schema OpenAPI generato da drf-spectacular."""
    html = """<!DOCTYPE html>
<html>
<head>
    <title>Events Backoffice API</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
</head>
<body>
    <script id="api-reference" data-url="/docs/schema/"></script>
    <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
</body>
</html>"""
    return HttpResponse(html, content_type="text/html")
