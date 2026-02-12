from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render


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
