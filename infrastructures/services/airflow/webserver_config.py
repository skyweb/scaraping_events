from airflow.www.fab_security.manager import AUTH_REMOTE_USER

AUTH_TYPE = AUTH_REMOTE_USER
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Admin"
AUTH_REMOTE_USER_ENV_VAR = "HTTP_X_AUTH_REQUEST_EMAIL"

# Evita conflitto con il cookie "session" di APISIX (lua-resty-session)
SESSION_COOKIE_NAME = "airflow_session"