from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.http import HttpResponse
from django.views.static import serve
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView

from backoffice.views import admin_sso_logout, permission_denied_view, api_version_view, api_version_drf_view, scalar_view, services_dashboard, openapi_download_view
from backoffice.waf_views import waf_rules_list, waf_rules_add, waf_rules_delete, waf_rules_test, waf_toggle

# ... (rest of the file) ...

handler403 = 'backoffice.views.permission_denied_view' # Set the custom 403 handler



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
    # Logout SSO: deve stare PRIMA di admin/ per intercettare /admin/logout/
    # Django logout cancella la sessione, poi APISIX/Keycloak gestisce il logout OIDC
    path('admin/logout/', admin_sso_logout, name='admin-sso-logout'),
    path('admin/', admin.site.urls),
    path('version/', api_version_drf_view, name='version'),
    path('api/version/', api_version_drf_view, name='api-version'),
    path('api/', include('events.urls')),
    path('api/comuni-istat/', include('comuni_italiani.urls')),
    path('api/cms/', include('cms.urls')),
    path('api/scraping/', include('scraping.urls')),
    path('api/ai-transform/', include('ai_transform.urls')),

    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', scalar_view, name='scalar-docs'),
    path('docs/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('docs/schema/', SpectacularAPIView.as_view(), name='public-schema'),
    path('docs/postman/', openapi_download_view, name='openapi-download'),

    # WAF management API
    path('api/waf/rules/', waf_rules_list, name='waf-rules-list'),
    path('api/waf/rules/add/', waf_rules_add, name='waf-rules-add'),
    path('api/waf/rules/<str:rule_id>/delete/', waf_rules_delete, name='waf-rules-delete'),
    path('api/waf/rules/test/', waf_rules_test, name='waf-rules-test'),
    path('api/waf/toggle/', waf_toggle, name='waf-toggle'),

    # CKEditor 5 (upload immagini/file)
    path('ckeditor5/', include('django_ckeditor_5.urls')),

    # Prometheus metrics (espone /metrics)
    path('', include('django_prometheus.urls')),

    # Frontend React su /report
    re_path(r'^report/assets/(?P<path>.*)$', serve_frontend_assets),
    re_path(r'^report(?:/.*)?$', serve_frontend, name='frontend-report'),

    # Dashboard servizi (home — deve essere ultimo)
    path('', services_dashboard, name='services-dashboard'),
]

# Serve media in development
if settings.DEBUG:
    from django.conf.urls.static import static
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
