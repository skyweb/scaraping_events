"""
Autenticazione JWT Keycloak per Django REST Framework.

Valida i token Bearer emessi da Keycloak scaricando le chiavi JWKS
dal realm configurato. Supporta cache delle chiavi con TTL di 5 minuti.
"""

import logging
from typing import Any

import jwt
import requests as http_client
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission
from rest_framework.request import Request

logger = logging.getLogger(__name__)

User = get_user_model()

_JWKS_CACHE_KEY = "keycloak_jwks"
_JWKS_CACHE_TTL: int = 300  # 5 minuti


class KeycloakUser:
    """
    Utente fittizio per token JWT validi senza corrispondenza nel DB Django.
    Simula un AnonymousUser ma con is_authenticated=True.
    """

    def __init__(self, sub: str, roles: list[str] | None = None) -> None:
        self.pk = None
        self.id = None
        self.sub = sub
        self.username = sub
        self.is_active = True
        self.is_staff = False
        self.is_superuser = False
        self.roles = roles or []

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def get_username(self) -> str:
        return self.username

    def __str__(self) -> str:
        return f"KeycloakUser(sub={self.sub})"


from api_consumers.metrics import api_consumer_auth_total, api_consumer_expired_total

VALID_PLANS = {"free", "enterprise", "flat"}


class ApisixConsumerAuthentication(BaseAuthentication):
    """
    Autenticazione via header X-Consumer-Plan iniettato da APISIX (key-auth consumer).

    Se presente l'header X-Consumer-Plan e non c'è un Bearer token,
    crea un KeycloakUser con scopes read+write (i permessi effettivi
    sono gestiti dal piano nella view).
    Se c'è un Bearer token, ritorna None per delegare a KeycloakJWTAuthentication.
    """

    def authenticate(self, request: Request) -> tuple[KeycloakUser, dict[str, list[str] | str]] | None:
        # Se c'è un Bearer token, delega all'auth JWT
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header and auth_header.lower().startswith("bearer "):
            return None

        plan = request.META.get("HTTP_X_CONSUMER_PLAN", "")
        if not plan or plan not in VALID_PLANS:
            return None

        username = request.META.get("HTTP_X_CONSUMER_USERNAME", f"api-key-{plan}")

        # Verifica scadenza consumer
        from api_consumers.models import ApiConsumer
        try:
            consumer = ApiConsumer.objects.get(username=username)
            if consumer.is_expired:
                api_consumer_expired_total.labels(
                    consumer=username, plan=plan, auth_type="api_key",
                ).inc()
                logger.warning(
                    "Accesso negato: consumer API key scaduto",
                    extra={"consumer": username, "plan": plan,
                           "expires_at": str(consumer.expires_at)},
                )
                raise AuthenticationFailed(
                    f"API consumer '{username}' scaduto il "
                    f"{consumer.expires_at.strftime('%d/%m/%Y %H:%M')}. "
                    f"Contattare l'amministratore per il rinnovo."
                )
        except ApiConsumer.DoesNotExist:
            pass  # Consumer non gestito da Django (es. test key da init-routes.sh)

        api_consumer_auth_total.labels(
            consumer=username, plan=plan, auth_type="api_key", status="success",
        ).inc()

        user = KeycloakUser(sub=username, roles=[])
        auth_info: dict[str, list[str] | str] = {
            "roles": [],
            "scope": ["read", "write"],
            "azp": f"{plan}-consumer",
            "sub": username,
            "plan": plan,
            "consumer_username": username,
        }

        logger.info(
            "Autenticazione API key (APISIX consumer)",
            extra={"plan": plan, "consumer": username},
        )

        return user, auth_info


class KeycloakJWTAuthentication(BaseAuthentication):
    """
    Backend di autenticazione DRF che valida token JWT Bearer emessi da Keycloak.

    Configurazione richiesta in settings.py:
        KEYCLOAK_URL      - URL base di Keycloak (es. http://keycloak:8080)
        KEYCLOAK_REALM    - Nome del realm (es. today-events)
        KEYCLOAK_AUDIENCE - Audience attesa nel token (es. account)

    Restituisce:
        (user, auth_info) dove auth_info è un dict con roles, scope, azp, sub.
        None se l'header Authorization non è di tipo Bearer.

    Solleva:
        AuthenticationFailed per token invalidi, scaduti o con issuer errato.
    """

    def authenticate(self, request: Request) -> tuple[Any, dict[str, Any]] | None:
        """Autentica la richiesta validando il token JWT Bearer."""
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None

        token = parts[1]
        return self._authenticate_token(token)

    def _authenticate_token(self, token: str) -> tuple[Any, dict[str, Any]]:
        """Valida il token JWT e restituisce (user, auth_info)."""
        jwks = self._get_jwks()
        audience = settings.KEYCLOAK_AUDIENCE

        # Issuer accettati: URL interno (Docker) e URL pubblico (APISIX)
        issuers = [f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}"]
        public_url = getattr(settings, "KEYCLOAK_PUBLIC_URL", "")
        if public_url:
            issuers.append(f"{public_url}/realms/{settings.KEYCLOAK_REALM}")

        try:
            # Decodifica l'header per trovare il kid
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")

            # Cerca la chiave pubblica corrispondente nel JWKS
            public_key = None
            for key_data in jwks.get("keys", []):
                if key_data.get("kid") == kid:
                    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)
                    break

            if public_key is None:
                raise AuthenticationFailed("Chiave pubblica non trovata nel JWKS per il kid specificato.")

            # Valida firma, audience e scadenza (issuer validato manualmente)
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=audience,
                options={"require": ["exp", "iss", "aud"], "verify_iss": False},
            )

            # Valida issuer manualmente (accetta interno o pubblico)
            token_issuer = payload.get("iss", "")
            if token_issuer not in issuers:
                raise AuthenticationFailed(
                    f"Issuer del token non valido: {token_issuer}. "
                    f"Attesi: {', '.join(issuers)}"
                )
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed("Token scaduto.")
        except jwt.InvalidIssuerError:
            raise AuthenticationFailed("Issuer del token non valido.")
        except jwt.InvalidAudienceError:
            raise AuthenticationFailed("Audience del token non valida.")
        except jwt.DecodeError as e:
            raise AuthenticationFailed(f"Token JWT non valido: {e}")
        except jwt.PyJWTError as e:
            raise AuthenticationFailed(f"Errore nella validazione del token: {e}")

        # Estrai ruoli e scope dal payload
        roles = payload.get("realm_access", {}).get("roles", [])
        scope_str = payload.get("scope", "")
        scope = scope_str.split() if scope_str else []
        azp = payload.get("azp", "")
        sub = payload.get("sub", "")
        plan = payload.get("plan", "")

        # Verifica scadenza consumer (se gestito da Django)
        from api_consumers.models import ApiConsumer
        consumer_username = azp  # Per JWT, azp è il client_id Keycloak
        try:
            consumer = ApiConsumer.objects.get(keycloak_client_id=azp)
            consumer_username = consumer.username
            if consumer.is_expired:
                api_consumer_expired_total.labels(
                    consumer=consumer.username, plan=plan or consumer.plan,
                    auth_type="jwt",
                ).inc()
                logger.warning(
                    "Accesso negato: consumer JWT scaduto",
                    extra={"consumer": consumer.username, "azp": azp,
                           "expires_at": str(consumer.expires_at)},
                )
                raise AuthenticationFailed(
                    f"API consumer '{consumer.username}' scaduto il "
                    f"{consumer.expires_at.strftime('%d/%m/%Y %H:%M')}. "
                    f"Contattare l'amministratore per il rinnovo."
                )
        except ApiConsumer.DoesNotExist:
            pass

        api_consumer_auth_total.labels(
            consumer=consumer_username, plan=plan, auth_type="jwt", status="success",
        ).inc()

        # Cerca un utente Django corrispondente, altrimenti crea un KeycloakUser
        user = self._get_or_create_keycloak_user(sub, roles)

        auth_info: dict[str, Any] = {
            "roles": roles,
            "scope": scope,
            "azp": azp,
            "sub": sub,
            "plan": plan,
            "consumer_username": consumer_username,
        }

        logger.info(
            "Autenticazione JWT riuscita",
            extra={"sub": sub, "azp": azp, "roles": roles, "plan": plan},
        )

        return user, auth_info

    def _get_or_create_keycloak_user(self, sub: str, roles: list[str]) -> Any:
        """
        Cerca un utente Django con username uguale al sub del token.
        Se non esiste, restituisce un KeycloakUser fittizio con is_authenticated=True.
        """
        try:
            return User.objects.get(username=sub)
        except User.DoesNotExist:
            return KeycloakUser(sub=sub, roles=roles)

    def _get_jwks(self) -> dict[str, Any]:
        """
        Scarica le chiavi JWKS dal Keycloak realm.
        Thread-safe tramite django.core.cache (Redis).
        """
        cached = cache.get(_JWKS_CACHE_KEY)
        if cached is not None:
            return cached

        jwks_url = (
            f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}"
            f"/protocol/openid-connect/certs"
        )

        try:
            response = http_client.get(jwks_url, timeout=10)
            response.raise_for_status()
            jwks_data = response.json()
            cache.set(_JWKS_CACHE_KEY, jwks_data, timeout=_JWKS_CACHE_TTL)
            logger.info("JWKS scaricato e cachato da %s", jwks_url)
            return jwks_data
        except (http_client.RequestException, OSError) as e:
            raise AuthenticationFailed(f"Impossibile scaricare le chiavi JWKS: {e}")


class HasKeycloakRole(BasePermission):
    """
    Permesso DRF che verifica che l'utente abbia almeno uno dei ruoli richiesti.

    Configurare nella view:
        required_roles = ["admin", "editor"]

    Basta che l'utente abbia ALMENO UNO dei ruoli elencati (logica OR).
    """

    def has_permission(self, request: Request, view: Any) -> bool:
        required_roles: list[str] = getattr(view, "required_roles", [])
        if not required_roles:
            return True

        auth_info = getattr(request, "auth", None)
        if not isinstance(auth_info, dict):
            return False

        user_roles: list[str] = auth_info.get("roles", [])
        # Almeno un ruolo deve corrispondere
        return bool(set(required_roles) & set(user_roles))


class HasKeycloakScope(BasePermission):
    """
    Permesso DRF che verifica che l'utente abbia tutti gli scope richiesti.

    Configurare nella view:
        required_scopes = ["read", "write"]

    L'utente deve avere TUTTI gli scope elencati (logica AND).
    """

    def has_permission(self, request: Request, view: Any) -> bool:
        required_scopes: list[str] = getattr(view, "required_scopes", [])
        if not required_scopes:
            return True

        auth_info = getattr(request, "auth", None)
        if not isinstance(auth_info, dict):
            return False

        user_scopes: list[str] = auth_info.get("scope", [])
        # Tutti gli scope richiesti devono essere presenti
        return set(required_scopes).issubset(set(user_scopes))
