"""
Test per l'autenticazione JWT Keycloak in Django REST Framework.

Genera una coppia di chiavi RSA per firmare token JWT di test,
mockando il download delle chiavi JWKS da Keycloak.
"""

import time
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import TestCase, RequestFactory, override_settings
from rest_framework.exceptions import AuthenticationFailed

from backoffice.authentication import KeycloakJWTAuthentication


# --- Generazione chiavi RSA per i test ---
_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_public_key = _private_key.public_key()

# Converti la chiave pubblica in formato JWK per simulare il JWKS
_public_key_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(_public_key, as_dict=True)
_public_key_jwk["kid"] = "test-kid-001"
_public_key_jwk["use"] = "sig"
_public_key_jwk["alg"] = "RS256"

# JWKS fittizio come lo restituirebbe Keycloak
MOCK_JWKS = {"keys": [_public_key_jwk]}

# Chiave privata in formato PEM per firmare i token
_private_key_pem = _private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)

# Configurazione Keycloak di test
TEST_KEYCLOAK_URL = "http://keycloak:8080"
TEST_KEYCLOAK_REALM = "today-events"
TEST_KEYCLOAK_AUDIENCE = "account"
TEST_ISSUER = f"{TEST_KEYCLOAK_URL}/realms/{TEST_KEYCLOAK_REALM}"


def _create_token(
    sub: str = "test-user-uuid",
    roles: list[str] | None = None,
    scope: str = "openid profile",
    issuer: str = TEST_ISSUER,
    audience: str = TEST_KEYCLOAK_AUDIENCE,
    exp_offset: int = 3600,
    kid: str = "test-kid-001",
) -> str:
    """Crea un token JWT firmato con la chiave RSA di test."""
    now = int(time.time())
    payload = {
        "sub": sub,
        "iss": issuer,
        "aud": audience,
        "exp": now + exp_offset,
        "iat": now,
        "azp": "scraping-service",
        "scope": scope,
        "realm_access": {"roles": roles or ["default-roles"]},
    }
    return jwt.encode(
        payload,
        _private_key_pem,
        algorithm="RS256",
        headers={"kid": kid},
    )


@override_settings(
    KEYCLOAK_URL=TEST_KEYCLOAK_URL,
    KEYCLOAK_REALM=TEST_KEYCLOAK_REALM,
    KEYCLOAK_AUDIENCE=TEST_KEYCLOAK_AUDIENCE,
)
class TestKeycloakJWTAuthentication(TestCase):
    """Test per KeycloakJWTAuthentication."""

    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.auth = KeycloakJWTAuthentication()

    def _make_request(self, token: str | None = None):
        """Crea una richiesta HTTP con header Authorization Bearer."""
        request = self.factory.get("/api/test/")
        if token is not None:
            request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return request

    @patch("backoffice.authentication.KeycloakJWTAuthentication._get_jwks")
    def test_valid_token_authenticates(self, mock_jwks):
        """Un token valido deve autenticare correttamente l'utente."""
        mock_jwks.return_value = MOCK_JWKS
        token = _create_token()
        request = self._make_request(token)

        result = self.auth.authenticate(request)

        self.assertIsNotNone(result)
        user, auth_info = result
        self.assertTrue(user.is_authenticated)
        self.assertEqual(auth_info["sub"], "test-user-uuid")
        self.assertEqual(auth_info["azp"], "scraping-service")

    @patch("backoffice.authentication.KeycloakJWTAuthentication._get_jwks")
    def test_expired_token_raises(self, mock_jwks):
        """Un token scaduto deve sollevare AuthenticationFailed."""
        mock_jwks.return_value = MOCK_JWKS
        token = _create_token(exp_offset=-3600)  # Scaduto un'ora fa
        request = self._make_request(token)

        with self.assertRaises(AuthenticationFailed) as ctx:
            self.auth.authenticate(request)
        self.assertIn("scaduto", str(ctx.exception.detail).lower())

    @patch("backoffice.authentication.KeycloakJWTAuthentication._get_jwks")
    def test_wrong_issuer_raises(self, mock_jwks):
        """Un token con issuer errato deve sollevare AuthenticationFailed."""
        mock_jwks.return_value = MOCK_JWKS
        token = _create_token(issuer="http://evil-server:8080/realms/fake")
        request = self._make_request(token)

        with self.assertRaises(AuthenticationFailed) as ctx:
            self.auth.authenticate(request)
        self.assertIn("issuer", str(ctx.exception.detail).lower())

    def test_no_auth_header_returns_none(self):
        """Senza header Authorization, deve restituire None."""
        request = self.factory.get("/api/test/")
        result = self.auth.authenticate(request)
        self.assertIsNone(result)

    def test_non_bearer_header_returns_none(self):
        """Un header Authorization non-Bearer deve restituire None."""
        request = self.factory.get("/api/test/")
        request.META["HTTP_AUTHORIZATION"] = "Basic dXNlcjpwYXNz"
        result = self.auth.authenticate(request)
        self.assertIsNone(result)

    @patch("backoffice.authentication.KeycloakJWTAuthentication._get_jwks")
    def test_roles_extracted_from_realm_access(self, mock_jwks):
        """I ruoli devono essere estratti dal claim realm_access.roles."""
        mock_jwks.return_value = MOCK_JWKS
        roles = ["admin", "editor", "viewer"]
        token = _create_token(roles=roles)
        request = self._make_request(token)

        result = self.auth.authenticate(request)

        self.assertIsNotNone(result)
        _, auth_info = result
        self.assertEqual(auth_info["roles"], roles)
        self.assertIn("admin", auth_info["roles"])
        self.assertIn("editor", auth_info["roles"])
        self.assertIn("viewer", auth_info["roles"])
