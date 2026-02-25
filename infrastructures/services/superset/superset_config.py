"""
Configurazione Apache Superset per l'ambiente Today Events.
Legge le credenziali da variabili d'ambiente passate da docker-compose.
"""
import os

# Chiave segreta Flask - CAMBIARE IN PRODUZIONE
SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY", "superset-secret-change-me")

# URL database metadati Superset (separato dal DB applicativo)
_db_user = os.environ.get("DATABASE_USER", "events")
_db_password = os.environ.get("DATABASE_PASSWORD", "")
_db_host = os.environ.get("DATABASE_HOST", "postgres")
_db_port = os.environ.get("DATABASE_PORT", "5432")
_db_name = os.environ.get("DATABASE_DB", "superset")

SQLALCHEMY_DATABASE_URI = (
    f"postgresql+psycopg2://{_db_user}:{_db_password}@{_db_host}:{_db_port}/{_db_name}"
)

# Cache Redis - usa DB 3 e 4 per non conflitare con Django (usa DB 0,1,2)
_redis_host = os.environ.get("REDIS_HOST", "redis")
_redis_port = os.environ.get("REDIS_PORT", "6379")
_redis_password = os.environ.get("REDIS_PASSWORD", "")

if _redis_password:
    _redis_base_url = f"redis://:{_redis_password}@{_redis_host}:{_redis_port}"
else:
    _redis_base_url = f"redis://{_redis_host}:{_redis_port}"

CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "superset_",
    "CACHE_REDIS_URL": f"{_redis_base_url}/3",
}

# Cache risultati query SQL
DATA_CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 600,
    "CACHE_KEY_PREFIX": "superset_data_",
    "CACHE_REDIS_URL": f"{_redis_base_url}/4",
}

# Feature flags utili per dashboard eventi
FEATURE_FLAGS = {
    "ENABLE_TEMPLATE_PROCESSING": True,
    "DASHBOARD_NATIVE_FILTERS": True,
    "DASHBOARD_CROSS_FILTERS": True,
    "LISTVIEWS_DEFAULT_CARD_VIEW": True,
}

# Timeout query SQL (secondi)
SQLLAB_TIMEOUT = 300
SUPERSET_WEBSERVER_TIMEOUT = 300

# Sub-path /superset/ via nginx
# ProxyFix legge X-Forwarded-Prefix inviato da nginx e riscrive gli URL generati
ENABLE_PROXY_FIX = True
PROXY_FIX_CONFIG = {"x_for": 1, "x_proto": 1, "x_host": 1, "x_prefix": 1}

# Nota: per SSO automatico via oauth2-proxy header "Remote-User" sarebbe necessario
# un middleware WSGI che mappi HTTP_REMOTE_USER → REMOTE_USER nell'environ.
# In dev si usa AUTH_DB (default) con login admin/admin dalla form Superset.
# La form di login è raggiungibile su /superset/login/ (nginx strippa → /login/).
