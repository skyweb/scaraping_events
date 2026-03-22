"""
Airflow webserver config — SSO via APISIX/Keycloak (auth proxy).

APISIX inietta:
  - X-Auth-Request-Email: email utente (da userinfo)
  - X-Auth-Request-Roles: ruoli realm Keycloak separati da virgola

Mapping ruoli Keycloak → Airflow:
  - admin      → Admin (accesso completo)
  - monitoring → Viewer (sola lettura)
  - nessuno    → accesso negato
"""
import logging

from airflow.www.fab_security.manager import AUTH_REMOTE_USER
from airflow.www.security_manager import AirflowSecurityManagerV2
from flask import request

log = logging.getLogger(__name__)

# Mapping ruoli Keycloak → ruoli Airflow (primo match vince, ordine priorità)
KEYCLOAK_ROLE_MAP = {
    "admin": "Admin",
    "monitoring": "Viewer",
}


class KeycloakRoleSecurityManager(AirflowSecurityManagerV2):
    """Security manager che assegna il ruolo Airflow in base ai ruoli Keycloak.
    Se l'utente non ha né 'admin' né 'monitoring', l'accesso viene negato.
    """

    def _get_airflow_role_from_headers(self) -> str | None:
        """Legge X-Auth-Request-Roles e restituisce il ruolo Airflow corrispondente.
        Restituisce None se nessun ruolo Keycloak corrisponde.
        """
        roles_header = request.headers.get("X-Auth-Request-Roles", "")
        if not roles_header:
            return None

        keycloak_roles = [r.strip() for r in roles_header.split(",")]
        for kc_role, airflow_role in KEYCLOAK_ROLE_MAP.items():
            if kc_role in keycloak_roles:
                return airflow_role

        return None

    def auth_user_registration(self, userinfo) -> bool:
        """Blocca la registrazione se l'utente non ha ruoli Keycloak validi."""
        role = self._get_airflow_role_from_headers()
        if role is None:
            email = request.headers.get("X-Auth-Request-Email", "?")
            log.warning("Accesso negato a %s: nessun ruolo admin/monitoring", email)
            return False
        return True

    def auth_user_registration_role_header(self, username: str) -> list[str]:
        """Restituisce i ruoli da assegnare all'utente alla registrazione."""
        role_name = self._get_airflow_role_from_headers()
        if role_name is None:
            return []
        log.info("Utente %s: ruolo Airflow = %s (da Keycloak)", username, role_name)
        return [role_name]

    def load_user(self, user_model):
        """Override: aggiorna il ruolo ad ogni accesso, disattiva se non autorizzato."""
        user = super().load_user(user_model)
        if user and hasattr(user, "username"):
            role_name = self._get_airflow_role_from_headers()
            if role_name is None:
                if user.is_active:
                    user.is_active = False
                    self.update_user(user)
                    log.warning("Utente %s disattivato: nessun ruolo admin/monitoring", user.username)
                return None
            # Riattiva e aggiorna ruolo
            role = self.find_role(role_name)
            changed = False
            if not user.is_active:
                user.is_active = True
                changed = True
            if role and role not in user.roles:
                user.roles = [role]
                changed = True
            if changed:
                self.update_user(user)
                log.info("Utente %s aggiornato → %s", user.username, role_name)
        return user


AUTH_TYPE = AUTH_REMOTE_USER
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Public"
AUTH_REMOTE_USER_ENV_VAR = "HTTP_X_AUTH_REQUEST_EMAIL"
SECURITY_MANAGER_CLASS = KeycloakRoleSecurityManager

# Evita conflitto con il cookie "session" di APISIX (lua-resty-session)
SESSION_COOKIE_NAME = "airflow_session"
