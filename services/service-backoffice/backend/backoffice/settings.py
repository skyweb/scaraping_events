import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

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
    'rest_framework',
    'oauth2_provider',
    'rest_framework_tracking',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
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
        'ENGINE': 'django.db.backends.postgresql',
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
    'TITLE': 'Events Staging API',
    'DESCRIPTION': '''
## API per Servizi Esterni

API REST per l'integrazione con servizi di terze parti per la gestione degli staging events.

### Autenticazione

Questa API utilizza **OAuth2 Client Credentials** per l'autenticazione.

1. Richiedi le credenziali (Client ID e Client Secret) all'amministratore
2. Ottieni un access token chiamando `/oauth/token/`
3. Usa il token nelle richieste con header `Authorization: Bearer <token>`

### Scopes

- `read` - Permette di leggere gli staging events
- `write` - Permette di creare, modificare ed eliminare staging events

### Rate Limiting

Le richieste API sono monitorate. Contatta l'amministratore per informazioni sui limiti.
    ''',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SECURITY': [
        {'OAuth2': ['read', 'write']},
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
            }
        }
    },
    'TAGS': [
        {'name': 'Staging Events', 'description': 'Gestione staging events'},
        {'name': 'Bulk Operations', 'description': 'Operazioni massive'},
    ],
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
