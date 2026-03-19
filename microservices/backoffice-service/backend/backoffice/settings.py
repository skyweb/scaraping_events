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

# Limite upload per richieste bulk (default Django: 2.5MB, insufficiente per batch con raw_data)
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20MB

INSTALLED_APPS = [
    'unfold',
    'unfold.contrib.filters',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    'django.forms',
    'django_prometheus',
    'rest_framework',
    'rest_framework_tracking',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'django_celery_beat',
    'django_celery_results',
    'django_ckeditor_5',
    'comuni_istat',
    'comuni_istat_ingestion',
    'etl',
    'scraping',
    'events',
    'cms',
    'ai_transform',
    'nlp',
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'backoffice.middleware.KeycloakAdminMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'backoffice.middleware.ApiVersionHeaderMiddleware',
    'backoffice.middleware.AdminRequestLoggingMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
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
        'ENGINE': 'django_prometheus.db.backends.postgis',
        'NAME': os.environ.get('POSTGRES_DB', 'today_events'),
        'USER': os.environ.get('POSTGRES_USER', 'events'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'events_secret_2026'),
        'HOST': os.environ.get('POSTGRES_HOST', 'postgres'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    }
}

# Cache Redis instrumentata (DB 2 — DB 0 Airflow, DB 1 Celery broker)
CACHES = {
    'default': {
        'BACKEND': 'django_prometheus.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('CACHE_REDIS_URL', 'redis://:redis_secret_2026@redis:6379/2'),
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
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

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
        'backoffice.authentication.KeycloakJWTAuthentication',
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

# Versioning API — applicato solo alle view esterne (ExternalStagingEventViewSet)
API_VERSION = 'v1'
API_ALLOWED_VERSIONS = ['v1']

# Keycloak (Identity Provider)
KEYCLOAK_URL = os.environ.get('KEYCLOAK_URL', 'http://keycloak:8080')
KEYCLOAK_REALM = os.environ.get('KEYCLOAK_REALM', 'today-events')
KEYCLOAK_AUDIENCE = os.environ.get('KEYCLOAK_AUDIENCE', 'account')
# URL pubblico Keycloak (per token emessi via browser/Postman con issuer esterno)
KEYCLOAK_PUBLIC_URL = os.environ.get('KEYCLOAK_PUBLIC_URL', '')

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
    'http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://localhost:80'
).split(',')

# Spectacular (API docs)
SPECTACULAR_SETTINGS = {
    'TITLE': 'Events Backoffice API',
    'DESCRIPTION': '''
## API REST - Events Backoffice

API per la gestione degli eventi, monitoraggio ETL e integrazione con servizi esterni.

### Autenticazione

- **API interne**: Session authentication (Django admin login)
- **API esterne** (`/api/external/v1/`): OAuth2 Client Credentials via Keycloak (versionata)
- **CMS** (`/api/cms/`): Pubblico, senza autenticazione
- **Comuni ISTAT Ingestion** (`/api/comuni-istat/`): Session authentication

#### OAuth2 Flow (Keycloak)

1. Richiedi le credenziali (Client ID e Client Secret) all'amministratore
2. Ottieni un access token: `POST /realms/today-events/protocol/openid-connect/token` con `grant_type=client_credentials`
3. Usa il token: `Authorization: Bearer <access_token>`

### Scopes OAuth2

- `read` - Lettura staging events
- `write` - Scrittura staging events

### Versioning

Le API esterne (`/api/external/`) sono versionate tramite URL path:
- Versione corrente: **v1** → `/api/external/v1/staging/`
- Endpoint info versione: `GET /api/version/` (senza autenticazione)
- Header `X-API-Version` presente in ogni risposta API

Le API interne (`/api/events/`, `/api/dashboard/`, ecc.) non sono versionate.
    ''',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SECURITY': [
        {'OAuth2': ['read', 'write']},
        {'SessionAuth': []},
    ],
    'OAUTH2_FLOWS': ['clientCredentials'],
    'OAUTH2_TOKEN_URL': f'{os.environ.get("KEYCLOAK_URL", "http://keycloak:8080")}/realms/{os.environ.get("KEYCLOAK_REALM", "today-events")}/protocol/openid-connect/token',
    'COMPONENTS': {
        'securitySchemes': {
            'OAuth2': {
                'type': 'oauth2',
                'flows': {
                    'clientCredentials': {
                        'tokenUrl': f'{os.environ.get("KEYCLOAK_URL", "http://keycloak:8080")}/realms/{os.environ.get("KEYCLOAK_REALM", "today-events")}/protocol/openid-connect/token',
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
        {'name': 'Staging Events', 'description': 'API esterna OAuth2 v1 - gestione staging events'},
        {'name': 'Bulk Operations', 'description': 'Operazioni massive (bulk create, clear source)'},
        {'name': 'CMS', 'description': 'Pagine città CMS: sezioni, articoli, eventi'},
        {'name': 'Comuni ISTAT Ingestion', 'description': 'Ingestione dati scraping comuni-italiani.it (raw JSON)'},
    ],
}

# Celery
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://:redis_secret_2026@redis:6379/1')
CELERY_RESULT_BACKEND = 'django-db'
CELERY_RESULT_EXTENDED = True
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_WORKER_HIJACK_ROOT_LOGGER = False  # Mantiene il formato LOGGING Django con trace_id
CELERY_WORKER_SEND_TASK_EVENTS = True
CELERY_TASK_SEND_SENT_EVENT = True

# CKEditor 5
CKEDITOR_5_CONFIGS = {
    'default': {
        'toolbar': {
            'items': [
                'heading', '|',
                'bold', 'italic', 'underline', 'strikethrough', '|',
                'fontSize', 'fontFamily', 'fontColor', 'fontBackgroundColor', '|',
                'alignment', '|',
                'link', 'imageUpload', 'insertTable', 'blockQuote', 'highlight', '|',
                'bulletedList', 'numberedList', 'todoList', '|',
                'outdent', 'indent', '|',
                'removeFormat', 'sourceEditing', 'undo', 'redo',
            ],
            'shouldNotGroupWhenFull': True,
        },
        'image': {
            'toolbar': [
                'imageTextAlternative', '|',
                'imageStyle:alignLeft', 'imageStyle:alignCenter', 'imageStyle:alignRight', '|',
                'imageStyle:full', 'imageStyle:side',
            ],
            'styles': [
                'full',
                'side',
                'alignLeft',
                'alignCenter',
                'alignRight',
            ]
        },
        'table': {
            'contentToolbar': [
                'tableColumn', 'tableRow', 'mergeTableCells',
                'tableProperties', 'tableCellProperties',
            ],
        },
        'heading': {
            'options': [
                {'model': 'paragraph', 'title': 'Paragrafo', 'class': 'ck-heading_paragraph'},
                {'model': 'heading2', 'view': 'h2', 'title': 'Titolo 2', 'class': 'ck-heading_heading2'},
                {'model': 'heading3', 'view': 'h3', 'title': 'Titolo 3', 'class': 'ck-heading_heading3'},
                {'model': 'heading4', 'view': 'h4', 'title': 'Titolo 4', 'class': 'ck-heading_heading4'},
            ],
        },
        'language': 'it',
    },
}
CKEDITOR_5_FILE_UPLOAD_PERMISSION = "staff"
CKEDITOR_5_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"

X_FRAME_OPTIONS = 'SAMEORIGIN'

# AI Providers (trasformazione eventi → Schema.org)
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')

# Logging JSON strutturato — Promtail/Loki parsano nativamente.
# Se OTel è attivo, il LoggingInstrumentor inietta otelTraceID/otelSpanID nel record
# e vengono inclusi automaticamente nel JSON output.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s',
            'rename_fields': {
                'asctime': 'timestamp',
                'levelname': 'level',
                'name': 'logger',
            },
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django.server': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'admin.requests': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'admin.sso': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery.task': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

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
                        "title": "Comuni (geo)",
                        "icon": "location_city",
                        "link": "/admin/comuni_istat/comuneitaliano/",
                    },
                    {
                        "title": "Province (geo)",
                        "icon": "map",
                        "link": "/admin/comuni_istat/provinciaitaliana/",
                    },
                ],
            },
            {
                "title": "Comuni Ingestion",
                "separator": True,
                "items": [
                    {
                        "title": "Regioni",
                        "icon": "public",
                        "link": "/admin/comuni_istat_ingestion/regione/",
                    },
                    {
                        "title": "Province",
                        "icon": "map",
                        "link": "/admin/comuni_istat_ingestion/provincia/",
                    },
                    {
                        "title": "Comuni",
                        "icon": "location_city",
                        "link": "/admin/comuni_istat_ingestion/comune/",
                    },
                    {
                        "title": "Appartenenze",
                        "icon": "groups",
                        "link": "/admin/comuni_istat_ingestion/comuneappartenenza/",
                    },
                    {
                        "title": "Raw Data",
                        "icon": "database",
                        "link": "/admin/comuni_istat_ingestion/comuniistatrawdata/",
                    },
                ],
            },
            {
                "title": "CMS",
                "separator": True,
                "items": [
                    {
                        "title": "Pagine Città",
                        "icon": "web",
                        "link": "/admin/cms/paginacitta/",
                    },
                    {
                        "title": "Sezioni",
                        "icon": "article",
                        "link": "/admin/cms/sezionepagina/",
                    },
                ],
            },
            {
                "title": "Scraping",
                "separator": True,
                "items": [
                    {
                        "title": "Websites",
                        "icon": "language",
                        "link": "/admin/scraping/scrapingwebsite/",
                    },
                    {
                        "title": "Categorie",
                        "icon": "category",
                        "link": "/admin/scraping/scrapingcategory/",
                    },
                    {
                        "title": "Location",
                        "icon": "place",
                        "link": "/admin/scraping/scrapinglocation/",
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
                        "link": "/admin/etl/etlrun/",
                    },
                    {
                        "title": "ETL Errors",
                        "icon": "error",
                        "link": "/admin/etl/etlerror/",
                    },
                ],
            },
            {
                "title": "API",
                "separator": True,
                "items": [
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

# =============================================================================
# Airflow API (per trigger DAG da admin)
# =============================================================================
AIRFLOW_API_URL = os.getenv('AIRFLOW_API_URL', 'http://airflow-webserver:8080/api/v1')
AIRFLOW_API_USER = os.getenv('AIRFLOW_API_USER', 'admin')
AIRFLOW_API_PASSWORD = os.getenv('AIRFLOW_API_PASSWORD', 'admin_secret_2026')
