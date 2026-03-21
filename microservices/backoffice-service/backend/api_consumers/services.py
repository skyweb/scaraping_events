"""
Servizi di sincronizzazione API consumers verso APISIX e Keycloak.

APISIX Admin API: crea/aggiorna/elimina consumers con key-auth + proxy-rewrite.
Keycloak Admin REST API: crea client con custom claim 'plan' nel token.
"""

import logging
import secrets
from typing import TYPE_CHECKING

import requests as http_client
from django.conf import settings

if TYPE_CHECKING:
    from api_consumers.models import ApiConsumer

logger = logging.getLogger(__name__)


# =============================================================================
# Helpers HTTP
# =============================================================================

def _http_request(
    method: str,
    url: str,
    data: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 10,
    params: dict[str, str] | None = None,
) -> dict:
    """Esegue una richiesta HTTP e restituisce il JSON di risposta."""
    response = http_client.request(
        method, url, json=data, headers=headers, timeout=timeout, params=params,
    )
    response.raise_for_status()
    return response.json() if response.content else {}


def _apisix_request(method: str, path: str, data: dict | None = None) -> dict:
    """Richiesta all'Admin API di APISIX."""
    url = f"{settings.APISIX_ADMIN_URL}{path}"
    return _http_request(method, url, data, {"X-API-KEY": settings.APISIX_ADMIN_KEY})


# =============================================================================
# APISIX — Consumer CRUD
# =============================================================================

def sync_consumer_to_apisix(consumer: "ApiConsumer") -> None:
    """Crea o aggiorna un consumer APISIX con key-auth e proxy-rewrite."""
    # Consumer disattivato o scaduto → rimuovi da APISIX
    if not consumer.is_active or consumer.is_expired:
        try:
            delete_consumer_from_apisix(consumer.username)
            logger.info(
                "Consumer APISIX rimosso (%s): %s",
                "scaduto" if consumer.is_expired else "disattivato",
                consumer.username,
            )
        except Exception:
            logger.warning("Errore rimozione consumer APISIX %s", consumer.username, exc_info=True)
        return

    data: dict = {
        "username": consumer.username,
        "plugins": {
            "key-auth": {
                "key": consumer.api_key,
            },
            "proxy-rewrite": {
                "headers": {
                    "set": {
                        "X-Consumer-Plan": consumer.plan,
                        "X-Consumer-Username": consumer.username,
                        "X-Forwarded-Proto": "https",
                    }
                }
            },
        },
    }

    # Solo il piano free ha un consumer group con rate limiting
    if consumer.plan == "free":
        data["group_id"] = "free"

    _apisix_request("PUT", f"/consumers/{consumer.username}", data)
    logger.info("Consumer APISIX sincronizzato: %s (piano %s)", consumer.username, consumer.plan)


def delete_consumer_from_apisix(username: str) -> None:
    """Rimuove un consumer da APISIX."""
    _apisix_request("DELETE", f"/consumers/{username}")
    logger.info("Consumer APISIX eliminato: %s", username)


def get_consumer_from_apisix(username: str) -> dict:
    """Recupera un consumer da APISIX."""
    return _apisix_request("GET", f"/consumers/{username}")


# =============================================================================
# Keycloak Admin REST API
# =============================================================================

def _get_keycloak_admin_token() -> str:
    """Ottiene un access token per l'Admin REST API di Keycloak via client credentials."""
    token_url = (
        f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}"
        f"/protocol/openid-connect/token"
    )
    response = http_client.post(
        token_url,
        data={
            "grant_type": "client_credentials",
            "client_id": settings.APISIX_KC_CLIENT_ID,
            "client_secret": settings.APISIX_KC_CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def sync_consumer_to_keycloak(consumer: "ApiConsumer") -> None:
    """
    Crea un client Keycloak con client_credentials grant e custom claim 'plan'.

    Se il client esiste già (stesso client_id), aggiorna il mapper del piano.
    """
    token = _get_keycloak_admin_token()
    base_url = f"{settings.KEYCLOAK_URL}/admin/realms/{settings.KEYCLOAK_REALM}"
    auth_headers = {"Authorization": f"Bearer {token}"}

    client_id = consumer.keycloak_client_id or f"api-{consumer.username}"

    # Cerca client esistente
    existing = _http_request(
        "GET",
        f"{base_url}/clients",
        headers=auth_headers,
        params={"clientId": client_id},
    )

    # Il client Keycloak è abilitato solo se il consumer è attivo e non scaduto
    should_be_enabled = consumer.is_active and not consumer.is_expired

    if existing:
        # Client esiste → aggiorna enabled + mapper
        kc_id = existing[0]["id"]
        if existing[0].get("enabled") != should_be_enabled:
            existing[0]["enabled"] = should_be_enabled
            _http_request("PUT", f"{base_url}/clients/{kc_id}", existing[0], auth_headers)
            logger.info(
                "Client Keycloak %s: %s",
                "abilitato" if should_be_enabled else "disabilitato",
                client_id,
            )
        # Recupera credenziali se mancanti localmente (es. sync precedente fallita)
        if not consumer.keycloak_client_id or not consumer.keycloak_client_secret:
            secret_resp = _http_request(
                "GET",
                f"{base_url}/clients/{kc_id}/client-secret",
                headers=auth_headers,
            )
            consumer.keycloak_client_id = client_id
            consumer.keycloak_client_secret = secret_resp.get("value", "")
    else:
        # Genera secret e crea client
        client_secret = consumer.keycloak_client_secret or secrets.token_urlsafe(32)

        client_data = {
            "clientId": client_id,
            "name": f"API Consumer: {consumer.username}",
            "enabled": should_be_enabled,
            "protocol": "openid-connect",
            "publicClient": False,
            "serviceAccountsEnabled": True,
            "standardFlowEnabled": False,
            "directAccessGrantsEnabled": False,
            "clientAuthenticatorType": "client-secret",
            "secret": client_secret,
            "defaultClientScopes": ["email", "profile"],
            "attributes": {
                "oauth2.device.authorization.grant.enabled": "false",
                "backchannel.logout.session.required": "true",
            },
        }

        _http_request("POST", f"{base_url}/clients", client_data, auth_headers)

        # Recupera l'ID interno del client appena creato
        created = _http_request(
            "GET",
            f"{base_url}/clients",
            headers=auth_headers,
            params={"clientId": client_id},
        )
        kc_id = created[0]["id"]

        # Recupera il secret effettivo
        secret_resp = _http_request(
            "GET",
            f"{base_url}/clients/{kc_id}/client-secret",
            headers=auth_headers,
        )
        consumer.keycloak_client_id = client_id
        consumer.keycloak_client_secret = secret_resp.get("value", client_secret)

    # Aggiungi/aggiorna mapper hardcoded claims (plan, username)
    mappers = _http_request(
        "GET",
        f"{base_url}/clients/{kc_id}/protocol-mappers/models",
        headers=auth_headers,
    )

    hardcoded_claims = {
        "plan": consumer.plan,
        "consumer_username": consumer.username,
    }

    for claim_name, claim_value in hardcoded_claims.items():
        existing_mapper = next((m for m in mappers if m.get("name") == claim_name), None)

        mapper_data = {
            "name": claim_name,
            "protocol": "openid-connect",
            "protocolMapper": "oidc-hardcoded-claim-mapper",
            "config": {
                "claim.name": claim_name,
                "claim.value": claim_value,
                "jsonType.label": "String",
                "id.token.claim": "true",
                "access.token.claim": "true",
                "userinfo.token.claim": "true",
            },
        }

        if existing_mapper:
            mapper_data["id"] = existing_mapper["id"]
            _http_request(
                "PUT",
                f"{base_url}/clients/{kc_id}/protocol-mappers/models/{existing_mapper['id']}",
                mapper_data,
                auth_headers,
            )
        else:
            _http_request(
                "POST",
                f"{base_url}/clients/{kc_id}/protocol-mappers/models",
                mapper_data,
                auth_headers,
            )

    logger.info(
        "Client Keycloak sincronizzato: %s (client_id=%s, piano=%s)",
        consumer.username, client_id, consumer.plan,
    )


def delete_client_from_keycloak(client_id: str) -> None:
    """Rimuove un client da Keycloak."""
    token = _get_keycloak_admin_token()
    base_url = f"{settings.KEYCLOAK_URL}/admin/realms/{settings.KEYCLOAK_REALM}"
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Trova l'ID interno
    clients = _http_request(
        "GET",
        f"{base_url}/clients",
        headers=auth_headers,
        params={"clientId": client_id},
    )
    if clients:
        kc_id = clients[0]["id"]
        _http_request("DELETE", f"{base_url}/clients/{kc_id}", headers=auth_headers)
        logger.info("Client Keycloak eliminato: %s", client_id)
