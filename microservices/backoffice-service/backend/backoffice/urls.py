from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView

from backoffice.views import admin_sso_logout, permission_denied_view, api_version_drf_view, scalar_view, scalar_public_view, services_dashboard, openapi_download_view
from backoffice.report_views import report_dashboard, report_events, report_etl_runs, report_etl_errors
from backoffice.waf_views import waf_rules_list, waf_rules_add, waf_rules_delete, waf_rules_test, waf_toggle

handler403 = 'backoffice.views.permission_denied_view'

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

    # API Documentation — schema interno (tutti gli endpoint)
    path('api/schema/', SpectacularAPIView.as_view(
        custom_settings={'PREPROCESSING_HOOKS': ['backoffice.openapi.internal_endpoint_filter']},
    ), name='schema'),
    path('docs/', scalar_view, name='scalar-docs'),
    path('docs/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('docs/schema/', SpectacularAPIView.as_view(
        custom_settings={'PREPROCESSING_HOOKS': ['backoffice.openapi.internal_endpoint_filter']},
    ), name='internal-schema'),

    # API Documentation — schema pubblico (/api/v1/events/, /version/)
    path('docs/public/', scalar_public_view, name='scalar-public-docs'),
    path('docs/public/schema/', SpectacularAPIView.as_view(
        custom_settings={'PREPROCESSING_HOOKS': ['backoffice.openapi.public_endpoint_filter']},
    ), name='public-schema'),
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

    # Report (Django templates)
    path('report/', report_dashboard, name='report-dashboard'),
    path('report/events/', report_events, name='report-events'),
    path('report/etl-runs/', report_etl_runs, name='report-etl-runs'),
    path('report/etl-errors/', report_etl_errors, name='report-etl-errors'),

    # Dashboard servizi (home — deve essere ultimo)
    path('', services_dashboard, name='services-dashboard'),
]

# Serve media in development
if settings.DEBUG:
    from django.conf.urls.static import static
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
