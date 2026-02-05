import os
import platform
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# GDAL/GEOS per macOS (development locale)
if platform.system() == 'Darwin':
    _gdal_path = Path('/opt/homebrew/lib/python3.11/site-packages/fiona/.dylibs/libgdal.32.3.6.4.dylib')
    _geos_path = Path('/opt/homebrew/lib/python3.11/site-packages/shapely/.dylibs/libgeos_c.1.17.3.dylib')
    if _gdal_path.exists():
        GDAL_LIBRARY_PATH = str(_gdal_path)
    if _geos_path.exists():
        GEOS_LIBRARY_PATH = str(_geos_path)

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-change-me-in-production')

DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() == 'true'

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'unfold',
    'unfold.contrib.filters',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.forms',
    'rest_framework',
    'oauth2_provider',
    'rest_framework_tracking',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'django_celery_beat',
    'django_celery_results',
    'comuni_italiani',
    'etl',
    'scraping',
    'events',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'backoffice.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backoffice.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.environ.get('POSTGRES_DB', 'today_events'),
        'USER': os.environ.get('POSTGRES_USER', 'events'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'events_secret_2026'),
        'HOST': os.environ.get('POSTGRES_HOST', 'postgres'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'it-it'
TIME_ZONE = 'Europe/Rome'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise configuration
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
}

# Frontend build directory
FRONTEND_DIR = BASE_DIR / 'staticfiles' / 'frontend'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Form Renderer
FORM_RENDERER = 'django.forms.renderers.TemplatesSetting'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'oauth2_provider.contrib.rest_framework.OAuth2Authentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# OAuth2 Provider
OAUTH2_PROVIDER = {
    'SCOPES': {
        'read': 'Read access to staging events',
        'write': 'Write access to staging events',
    },
    'ACCESS_TOKEN_EXPIRE_SECONDS': 36000,  # 10 hours
    'REFRESH_TOKEN_EXPIRE_SECONDS': 86400 * 30,  # 30 days
    'ROTATE_REFRESH_TOKEN': True,
}

# DRF API Tracking
DRF_TRACKING_ADMIN_LOG_READONLY = True

# CORS
CORS_ALLOWED_ORIGINS = os.environ.get(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:3000,http://127.0.0.1:3000'
).split(',')
CORS_ALLOW_CREDENTIALS = True

# CSRF
CSRF_TRUSTED_ORIGINS = os.environ.get(
    'CSRF_TRUSTED_ORIGINS',
    'http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000'
).split(',')

# Spectacular (API docs)
SPECTACULAR_SETTINGS = {
    'TITLE': 'Events Backoffice API',
    'DESCRIPTION': '''
## API REST - Events Backoffice

API per la gestione degli eventi, monitoraggio ETL e integrazione con servizi esterni.

### Autenticazione

- **API interne**: Session authentication (Django admin login)
- **API esterne** (`/api/external/`): OAuth2 Client Credentials

#### OAuth2 Flow

1. Richiedi le credenziali (Client ID e Client Secret) all'amministratore
2. Ottieni un access token: `POST /oauth/token/` con `grant_type=client_credentials`
3. Usa il token: `Authorization: Bearer <access_token>`

### Scopes OAuth2

- `read` - Lettura staging events
- `write` - Scrittura staging events
    ''',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SECURITY': [
        {'OAuth2': ['read', 'write']},
        {'SessionAuth': []},
    ],
    'OAUTH2_FLOWS': ['clientCredentials'],
    'OAUTH2_TOKEN_URL': '/oauth/token/',
    'COMPONENTS': {
        'securitySchemes': {
            'OAuth2': {
                'type': 'oauth2',
                'flows': {
                    'clientCredentials': {
                        'tokenUrl': '/oauth/token/',
                        'scopes': {
                            'read': 'Read access to staging events',
                            'write': 'Write access to staging events',
                        }
                    }
                }
            },
            'SessionAuth': {
                'type': 'apiKey',
                'in': 'cookie',
                'name': 'sessionid',
            }
        }
    },
    'TAGS': [
        {'name': 'Dashboard', 'description': 'Statistiche aggregate e panoramica'},
        {'name': 'Production Events', 'description': 'Eventi validati in produzione'},
        {'name': 'Staging Events (Internal)', 'description': 'Eventi in staging (sola lettura interna)'},
        {'name': 'ETL', 'description': 'Monitoraggio esecuzioni e errori ETL'},
        {'name': 'Staging Events', 'description': 'API esterna OAuth2 - gestione staging events'},
        {'name': 'Bulk Operations', 'description': 'Operazioni massive (bulk create, clear source)'},
    ],
}

# Celery
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://:redis_secret_2026@redis:6379/1')
CELERY_RESULT_BACKEND = 'django-db'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Unfold Admin Theme
UNFOLD = {
    "SITE_TITLE": "Events Backoffice",
    "SITE_HEADER": "Events Backoffice",
    "SITE_SYMBOL": "calendar_month",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "COLORS": {
        "primary": {
            "50": "250 245 255",
            "100": "243 232 255",
            "200": "233 213 255",
            "300": "216 180 254",
            "400": "192 132 252",
            "500": "168 85 247",
            "600": "147 51 234",
            "700": "126 34 206",
            "800": "107 33 168",
            "900": "88 28 135",
            "950": "59 7 100",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {
                "title": "Dashboard",
                "separator": True,
                "items": [
                    {
                        "title": "Home",
                        "icon": "home",
                        "link": "/admin/",
                    },
                ],
            },
            {
                "title": "Eventi",
                "separator": True,
                "items": [
                    {
                        "title": "Production Events",
                        "icon": "event",
                        "link": "/admin/events/productionevent/",
                    },
                    {
                        "title": "Staging Events",
                        "icon": "schedule",
                        "link": "/admin/events/stagingevent/",
                    },
                ],
            },
            {
                "title": "Comuni",
                "separator": True,
                "items": [
                    {
                        "title": "Comuni italiani",
                        "icon": "location_city",
                        "link": "/admin/comuni_italiani/comuneitaliano/",
                    },
                    {
                        "title": "Province",
                        "icon": "map",
                        "link": "/admin/comuni_italiani/provinciaitaliana/",
                    },
                ],
            },
            {
                "title": "Scraping",
                "separator": True,
                "items": [
                    {
                        "title": "Categorie",
                        "icon": "category",
                        "link": "/admin/events/scrapingcategoria/",
                    },
                    {
                        "title": "Location",
                        "icon": "place",
                        "link": "/admin/events/scrapinglocation/",
                    },
                ],
            },
            {
                "title": "ETL",
                "separator": True,
                "items": [
                    {
                        "title": "ETL Runs",
                        "icon": "sync",
                        "link": "/admin/events/etlrun/",
                    },
                    {
                        "title": "ETL Errors",
                        "icon": "error",
                        "link": "/admin/events/etlerror/",
                    },
                ],
            },
            {
                "title": "OAuth2 / API",
                "separator": True,
                "items": [
                    {
                        "title": "Applications",
                        "icon": "key",
                        "link": "/admin/oauth2_provider/application/",
                    },
                    {
                        "title": "Access Tokens",
                        "icon": "token",
                        "link": "/admin/oauth2_provider/accesstoken/",
                    },
                    {
                        "title": "API Requests Log",
                        "icon": "analytics",
                        "link": "/admin/rest_framework_tracking/apirequestlog/",
                    },
                ],
            },
            {
                "title": "Celery",
                "separator": True,
                "items": [
                    {
                        "title": "Periodic Tasks",
                        "icon": "timer",
                        "link": "/admin/django_celery_beat/periodictask/",
                    },
                    {
                        "title": "Task Results",
                        "icon": "checklist",
                        "link": "/admin/django_celery_results/taskresult/",
                    },
                ],
            },
            {
                "title": "Utenti",
                "separator": True,
                "items": [
                    {
                        "title": "Users",
                        "icon": "person",
                        "link": "/admin/auth/user/",
                    },
                    {
                        "title": "Groups",
                        "icon": "group",
                        "link": "/admin/auth/group/",
                    },
                ],
            },
        ],
    },
}
