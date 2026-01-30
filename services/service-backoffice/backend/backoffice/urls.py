from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.http import HttpResponse
from django.views.static import serve
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView


def serve_frontend(request, path=''):
    """Serve React frontend index.html for SPA routing"""
    index_path = settings.FRONTEND_DIR / 'index.html'
    if index_path.exists():
        with open(index_path, 'r') as f:
            return HttpResponse(f.read(), content_type='text/html')
    return HttpResponse('Frontend not found', status=404)


def serve_frontend_assets(request, path):
    """Serve frontend static assets (js, css, etc.)"""
    return serve(request, path, document_root=settings.FRONTEND_DIR / 'assets')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('events.urls')),

    # API Documentation (internal)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # Public API Documentation (external - no auth required for docs)
    path('docs/', SpectacularSwaggerView.as_view(url_name='public-schema'), name='public-swagger'),
    path('docs/redoc/', SpectacularRedocView.as_view(url_name='public-schema'), name='public-redoc'),
    path('docs/schema/', SpectacularAPIView.as_view(), name='public-schema'),

    # OAuth2 endpoints
    path('oauth/', include('oauth2_provider.urls', namespace='oauth2_provider')),

    # Frontend assets
    re_path(r'^assets/(?P<path>.*)$', serve_frontend_assets),

    # Catch-all for React SPA routing (must be last)
    re_path(r'^(?!admin|api|static|oauth|docs).*$', serve_frontend),
]
