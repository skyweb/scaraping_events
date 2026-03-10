# Migrazione Kong → APISIX + Keycloak — Piano di Implementazione

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sostituire Kong API Gateway + OAuth2 Proxy + Django OAuth Toolkit con Apache APISIX + Keycloak, centralizzando autenticazione e aggiungendo observability end-to-end.

**Architecture:** Traefik (edge/TLS) → APISIX (API gateway, plugin OIDC/JWT) → Django Backoffice. Keycloak come unico IdP per SSO browser (Google federato) e client credentials (scraper, airflow). OpenTelemetry trace end-to-end da Keycloak a Celery via Grafana/Tempo.

**Tech Stack:** Apache APISIX 3.11, etcd 3.5, Keycloak 26, Grafana Tempo, PyJWT, APISIX Ingress Controller (K8s CRD)

---

## Chunk 1: Infrastruttura Dev (docker-compose)

### Task 1: Keycloak Realm Template

**Files:**
- Create: `infrastructures/services/keycloak/realm-today-events.json`

- [ ] **Step 1: Crea il realm template JSON**

```json
{
  "realm": "today-events",
  "enabled": true,
  "displayName": "Today Events",
  "sslRequired": "external",
  "registrationAllowed": false,
  "loginWithEmailAllowed": true,
  "duplicateEmailsAllowed": false,
  "bruteForceProtected": true,
  "permanentLockout": false,
  "maxFailureWaitSeconds": 900,
  "failureFactor": 5,
  "accessTokenLifespan": 36000,
  "refreshTokenMaxReuse": 0,
  "ssoSessionIdleTimeout": 1800,
  "ssoSessionMaxLifespan": 36000,
  "offlineSessionIdleTimeout": 2592000,
  "eventsEnabled": true,
  "eventsListeners": ["jboss-logging", "metrics-listener"],
  "adminEventsEnabled": true,
  "adminEventsDetailsEnabled": true,
  "smtpServer": {},
  "roles": {
    "realm": [
      {
        "name": "admin",
        "description": "Amministratore backoffice"
      },
      {
        "name": "api-consumer",
        "description": "Consumatore API esterno"
      }
    ]
  },
  "scopeMappings": [],
  "clientScopes": [
    {
      "name": "read",
      "description": "Lettura staging events",
      "protocol": "openid-connect",
      "attributes": {
        "include.in.token.scope": "true",
        "display.on.consent.screen": "true"
      },
      "protocolMappers": [
        {
          "name": "read-scope-mapper",
          "protocol": "openid-connect",
          "protocolMapper": "oidc-hardcoded-claim-mapper",
          "config": {
            "claim.name": "scope",
            "claim.value": "read",
            "jsonType.label": "String",
            "id.token.claim": "false",
            "access.token.claim": "true"
          }
        }
      ]
    },
    {
      "name": "write",
      "description": "Scrittura staging events",
      "protocol": "openid-connect",
      "attributes": {
        "include.in.token.scope": "true",
        "display.on.consent.screen": "true"
      },
      "protocolMappers": [
        {
          "name": "write-scope-mapper",
          "protocol": "openid-connect",
          "protocolMapper": "oidc-hardcoded-claim-mapper",
          "config": {
            "claim.name": "scope",
            "claim.value": "write",
            "jsonType.label": "String",
            "id.token.claim": "false",
            "access.token.claim": "true"
          }
        }
      ]
    }
  ],
  "clients": [
    {
      "clientId": "backoffice-admin",
      "name": "Backoffice Admin SSO",
      "enabled": true,
      "publicClient": false,
      "standardFlowEnabled": true,
      "directAccessGrantsEnabled": false,
      "serviceAccountsEnabled": false,
      "authorizationServicesEnabled": false,
      "redirectUris": [
        "https://gateway.${DOMAIN}/*",
        "http://localhost:9080/*"
      ],
      "webOrigins": [
        "https://gateway.${DOMAIN}",
        "http://localhost:9080"
      ],
      "protocol": "openid-connect",
      "defaultClientScopes": ["openid", "profile", "email"],
      "optionalClientScopes": ["read", "write"],
      "secret": "CHANGE_ME_BACKOFFICE_SECRET"
    },
    {
      "clientId": "scraper-service",
      "name": "Scrapy Scraping Service",
      "enabled": true,
      "publicClient": false,
      "standardFlowEnabled": false,
      "directAccessGrantsEnabled": false,
      "serviceAccountsEnabled": true,
      "authorizationServicesEnabled": false,
      "protocol": "openid-connect",
      "defaultClientScopes": ["openid", "read", "write"],
      "secret": "CHANGE_ME_SCRAPER_SECRET"
    },
    {
      "clientId": "airflow-service",
      "name": "Airflow Orchestrator",
      "enabled": true,
      "publicClient": false,
      "standardFlowEnabled": false,
      "directAccessGrantsEnabled": false,
      "serviceAccountsEnabled": true,
      "authorizationServicesEnabled": false,
      "protocol": "openid-connect",
      "defaultClientScopes": ["openid", "read", "write"],
      "secret": "CHANGE_ME_AIRFLOW_SECRET"
    }
  ],
  "identityProviders": [
    {
      "alias": "google",
      "providerId": "google",
      "enabled": true,
      "trustEmail": true,
      "firstBrokerLoginFlowAlias": "first broker login",
      "config": {
        "clientId": "${GOOGLE_CLIENT_ID}",
        "clientSecret": "${GOOGLE_CLIENT_SECRET}",
        "defaultScope": "openid email profile",
        "syncMode": "IMPORT"
      }
    }
  ],
  "identityProviderMappers": [
    {
      "name": "admin-role-mapper",
      "identityProviderAlias": "google",
      "identityProviderMapper": "hardcoded-role-idp-mapper",
      "config": {
        "role": "admin"
      }
    }
  ]
}
```

- [ ] **Step 2: Commit**

```bash
git add infrastructures/services/keycloak/realm-today-events.json
git commit -m "feat(keycloak): realm template con client e Google IdP"
```

---

### Task 2: Configurazione APISIX Dev

**Files:**
- Create: `infrastructures/services/apisix/config.yaml`
- Create: `infrastructures/services/apisix/dashboard.yaml`

- [ ] **Step 1: Crea config APISIX**

File `infrastructures/services/apisix/config.yaml`:

```yaml
# APISIX configurazione sviluppo
apisix:
  node_listen: 9080
  enable_admin: true
  admin_listen:
    ip: 0.0.0.0
    port: 9180
  admin_key:
    - name: admin
      key: apisix-dev-admin-key
      role: admin

  ssl:
    enable: false

deployment:
  role: traditional
  role_traditional:
    config_provider: etcd
  etcd:
    host:
      - "http://etcd:2379"
    prefix: "/apisix"
    timeout: 30

plugin_attr:
  prometheus:
    export_addr:
      ip: 0.0.0.0
      port: 9091

  opentelemetry:
    trace_id_source: x-request-id
    resource:
      service.name: apisix-gateway
    collector:
      address: otel-collector:4317
      request_timeout: 3
    batch_span_processor:
      max_queue_size: 1024
      batch_timeout: 2

plugins:
  - openid-connect
  - jwt-auth
  - consumer-restriction
  - limit-count
  - cors
  - prometheus
  - opentelemetry
  - proxy-rewrite
  - response-rewrite
```

- [ ] **Step 2: Crea config Dashboard**

File `infrastructures/services/apisix/dashboard.yaml`:

```yaml
conf:
  listen:
    host: 0.0.0.0
    port: 9000
  etcd:
    endpoints:
      - "http://etcd:2379"
    prefix: "/apisix"
  log:
    error_log:
      level: warn
      file_path: /dev/stderr
    access_log:
      file_path: /dev/stdout

authentication:
  secret: apisix-dashboard-dev-secret
  expire_time: 3600
  users:
    - username: admin
      password: admin
```

- [ ] **Step 3: Commit**

```bash
git add infrastructures/services/apisix/
git commit -m "feat(apisix): configurazione APISIX e dashboard per dev"
```

---

### Task 3: Aggiorna docker-compose.dev.yml

**Files:**
- Modify: `infrastructures/docker-compose.dev.yml:703-764` (rimuovi kong)
- Modify: `infrastructures/docker-compose.dev.yml:800-824` (volumes)

- [ ] **Step 1: Sostituisci i servizi Kong (righe 703-764) con APISIX + etcd + Dashboard + Keycloak**

Rimuovi i blocchi `kong-migrations` (righe 704-720) e `kong` (righe 722-764).

Aggiungi al loro posto:

```yaml
  # etcd — store configurazione per APISIX
  etcd:
    image: bitnami/etcd:3.5
    container_name: dev-etcd
    restart: unless-stopped
    environment:
      ALLOW_NONE_AUTHENTICATION: "yes"
      ETCD_ADVERTISE_CLIENT_URLS: "http://etcd:2379"
      ETCD_LISTEN_CLIENT_URLS: "http://0.0.0.0:2379"
    volumes:
      - etcd-dev-data:/bitnami/etcd
    healthcheck:
      test: ["CMD", "etcdctl", "endpoint", "health"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      dev-network:
        aliases:
          - etcd

  # APISIX — API Gateway
  apisix:
    image: apache/apisix:3.11-debian
    container_name: dev-apisix
    restart: unless-stopped
    volumes:
      - ./services/apisix/config.yaml:/usr/local/apisix/conf/config.yaml:ro
    labels:
      - "traefik.enable=true"
      # API Gateway proxy
      - "traefik.http.routers.apisix-gateway.rule=Host(`gateway.${DOMAIN}`)"
      - "traefik.http.routers.apisix-gateway.entrypoints=websecure"
      - "traefik.http.routers.apisix-gateway.tls=true"
      - "traefik.http.routers.apisix-gateway.service=apisix-gateway-svc"
      - "traefik.http.services.apisix-gateway-svc.loadbalancer.server.port=9080"
    depends_on:
      etcd:
        condition: service_healthy
    networks:
      dev-network:
        aliases:
          - apisix

  # APISIX Dashboard — UI gestione route/plugin
  apisix-dashboard:
    image: apache/apisix-dashboard:3.0-alpine
    container_name: dev-apisix-dashboard
    restart: unless-stopped
    volumes:
      - ./services/apisix/dashboard.yaml:/usr/local/apisix-dashboard/conf/conf.yaml:ro
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.apisix-dashboard.rule=Host(`apisix.${DOMAIN}`)"
      - "traefik.http.routers.apisix-dashboard.entrypoints=websecure"
      - "traefik.http.routers.apisix-dashboard.tls=true"
      - "traefik.http.services.apisix-dashboard.loadbalancer.server.port=9000"
    depends_on:
      etcd:
        condition: service_healthy
    networks:
      dev-network:
        aliases:
          - apisix-dashboard

  # Keycloak — Identity Provider (SSO + Client Credentials)
  keycloak:
    image: quay.io/keycloak/keycloak:26.0
    container_name: dev-keycloak
    restart: unless-stopped
    command: start-dev --import-realm
    environment:
      KC_DB: postgres
      KC_DB_URL_HOST: postgres
      KC_DB_URL_PORT: "5432"
      KC_DB_URL_DATABASE: keycloak
      KC_DB_USERNAME: ${POSTGRES_USER}
      KC_DB_PASSWORD: ${POSTGRES_PASSWORD}
      KC_HEALTH_ENABLED: "true"
      KC_METRICS_ENABLED: "true"
      KC_TRACING_ENABLED: "true"
      KC_TRACING_ENDPOINT: "http://otel-collector:4317"
      KC_TRACING_JDBC_ENABLED: "true"
      KEYCLOAK_ADMIN: ${KEYCLOAK_ADMIN:-admin}
      KEYCLOAK_ADMIN_PASSWORD: ${KEYCLOAK_ADMIN_PASSWORD:-admin}
      KC_HTTP_PORT: "8080"
      KC_HOSTNAME_STRICT: "false"
      KC_PROXY_HEADERS: "xforwarded"
    volumes:
      - ./services/keycloak/realm-today-events.json:/opt/keycloak/data/import/realm-today-events.json:ro
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.keycloak.rule=Host(`keycloak.${DOMAIN}`)"
      - "traefik.http.routers.keycloak.entrypoints=websecure"
      - "traefik.http.routers.keycloak.tls=true"
      - "traefik.http.services.keycloak.loadbalancer.server.port=8080"
    healthcheck:
      test: ["CMD-SHELL", "exec 3<>/dev/tcp/localhost/9000 && echo -e 'GET /health/ready HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n' >&3 && cat <&3 | grep -q '\"status\":\"UP\"'"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 30s
    depends_on:
      postgres:
        condition: service_healthy
      otel-collector:
        condition: service_started
    networks:
      dev-network:
        aliases:
          - keycloak
```

- [ ] **Step 2: Aggiungi volume `etcd-dev-data` alla sezione volumes (riga ~800)**

Aggiungi dopo `sonarqube-dev-logs`:

```yaml
  etcd-dev-data:
    name: dev-etcd-data
```

- [ ] **Step 3: Verifica sintassi docker-compose**

Run: `cd /Users/skyweb/Sites/today_events/infrastructures && docker compose config --quiet`
Expected: nessun errore

- [ ] **Step 4: Commit**

```bash
git add infrastructures/docker-compose.dev.yml
git commit -m "feat(docker): sostituisci Kong con APISIX + etcd + Keycloak"
```

---

### Task 4: Aggiorna Database Init e Variabili

**Files:**
- Modify: `infrastructures/services/postgres/init.d/02-databases.sql:14-16` (kong → keycloak)
- Modify: `infrastructures/.env.example:81-82` (kong vars → keycloak vars)
- Modify: `infrastructures/services/prometheus/prometheus.yml:33-35` (kong → apisix)

- [ ] **Step 1: Sostituisci database kong con keycloak in 02-databases.sql**

Sostituisci righe 14-16:
```sql
-- Kong (API gateway)
SELECT 'CREATE DATABASE kong OWNER ' || current_user
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'kong') \gexec
```
con:
```sql
-- Keycloak (identity provider)
SELECT 'CREATE DATABASE keycloak OWNER ' || current_user
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'keycloak') \gexec
```

- [ ] **Step 2: Aggiorna .env.example — rimuovi Kong, aggiungi Keycloak + APISIX**

Sostituisci righe 81-82:
```
# Kong (API gateway)
KONG_PG_PASSWORD=events_secret_2026
```
con:
```
# Keycloak (Identity Provider)
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=admin_secret_2026

# API Authentication — Keycloak Client Credentials
# Genera client secret nella dashboard Keycloak: Realm > Clients > <client> > Credentials
KEYCLOAK_URL=http://keycloak:8080
KEYCLOAK_REALM=today-events
KEYCLOAK_SCRAPER_CLIENT_ID=scraper-service
KEYCLOAK_SCRAPER_CLIENT_SECRET=CHANGE_ME_SCRAPER_SECRET
KEYCLOAK_AIRFLOW_CLIENT_ID=airflow-service
KEYCLOAK_AIRFLOW_CLIENT_SECRET=CHANGE_ME_AIRFLOW_SECRET
```

Aggiorna anche righe 19-21 (API Authentication):
```
# API Authentication (for Airflow to call backoffice)
API_CLIENT_ID=airflow-client
API_CLIENT_SECRET=airflow-secret-change-in-production
```
con:
```
# API Authentication — Keycloak token endpoint
# Airflow e Scrapy ottengono JWT da Keycloak (client_credentials grant)
KEYCLOAK_TOKEN_URL=http://keycloak:8080/realms/today-events/protocol/openid-connect/token
API_CLIENT_ID=airflow-service
API_CLIENT_SECRET=CHANGE_ME_AIRFLOW_SECRET
```

- [ ] **Step 3: Aggiorna prometheus.yml — sostituisci kong con apisix**

Sostituisci righe 33-35:
```yaml
  - job_name: kong
    static_configs:
      - targets: ["kong:8100"]
```
con:
```yaml
  - job_name: apisix
    static_configs:
      - targets: ["apisix:9091"]

  - job_name: keycloak
    static_configs:
      - targets: ["keycloak:8080"]
    metrics_path: /metrics
```

- [ ] **Step 4: Commit**

```bash
git add infrastructures/services/postgres/init.d/02-databases.sql \
        infrastructures/.env.example \
        infrastructures/services/prometheus/prometheus.yml
git commit -m "feat(infra): aggiorna DB init, env vars e prometheus per APISIX+Keycloak"
```

---

### Task 5: Aggiorna Makefile

**Files:**
- Modify: `infrastructures/Makefile:126-134` (devtools target)

- [ ] **Step 1: Sostituisci kong con apisix/keycloak in up-devtools**

Sostituisci righe 126-134:
```makefile
up-devtools: ## Strumenti dev (kong, sonarqube, backstage, n8n)
	@echo "$(GREEN)Avvio devtools...$(NC)"
	$(COMPOSE) up -d kong-migrations kong sonarqube backstage n8n
	@echo ""
	@echo "$(CYAN)  https://kong.$(DOMAIN)/$(NC)             Kong Manager"
	@echo "$(CYAN)  https://sonarqube.$(DOMAIN)/$(NC)        SonarQube"
	@echo "$(CYAN)  https://backstage.$(DOMAIN)/$(NC)        Backstage"
	@echo "$(CYAN)  https://n8n.$(DOMAIN)/$(NC)              n8n"
	@echo ""
```
con:
```makefile
up-devtools: ## Strumenti dev (apisix, keycloak, sonarqube, backstage, n8n)
	@echo "$(GREEN)Avvio devtools...$(NC)"
	$(COMPOSE) up -d etcd apisix apisix-dashboard keycloak sonarqube backstage n8n
	@echo ""
	@echo "$(CYAN)  https://apisix.$(DOMAIN)/$(NC)           APISIX Dashboard"
	@echo "$(CYAN)  https://keycloak.$(DOMAIN)/$(NC)         Keycloak Admin"
	@echo "$(CYAN)  https://gateway.$(DOMAIN)/$(NC)          API Gateway"
	@echo "$(CYAN)  https://sonarqube.$(DOMAIN)/$(NC)        SonarQube"
	@echo "$(CYAN)  https://backstage.$(DOMAIN)/$(NC)        Backstage"
	@echo "$(CYAN)  https://n8n.$(DOMAIN)/$(NC)              n8n"
	@echo ""
```

Aggiorna anche il commento a riga 97:
```
#     up-devtools     strumenti dev (kong, sonarqube, backstage, n8n)
```
→
```
#     up-devtools     strumenti dev (apisix, keycloak, sonarqube, backstage, n8n)
```

- [ ] **Step 2: Commit**

```bash
git add infrastructures/Makefile
git commit -m "feat(makefile): aggiorna target devtools per APISIX+Keycloak"
```

---

### Task 6: Aggiungi Tempo al docker-compose (trace backend)

**Files:**
- Create: `infrastructures/services/tempo/tempo-config.yaml`
- Modify: `infrastructures/docker-compose.dev.yml` (aggiungi servizio tempo)
- Modify: `infrastructures/services/otel-collector/otel-collector-config.yaml` (esporta a Tempo)
- Modify: `infrastructures/services/grafana/provisioning/datasources/datasources.yaml` (aggiungi Tempo)

- [ ] **Step 1: Crea configurazione Tempo**

File `infrastructures/services/tempo/tempo-config.yaml`:

```yaml
# Grafana Tempo — configurazione sviluppo
server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: 0.0.0.0:4317
        http:
          endpoint: 0.0.0.0:4318

storage:
  trace:
    backend: local
    local:
      path: /var/tempo/traces
    wal:
      path: /var/tempo/wal

metrics_generator:
  registry:
    external_labels:
      source: tempo
  storage:
    path: /var/tempo/generator/wal
    remote_write:
      - url: http://prometheus:9090/api/v1/write
        send_exemplars: true

overrides:
  defaults:
    metrics_generator:
      processors:
        - service-graphs
        - span-metrics
```

- [ ] **Step 2: Aggiungi servizio Tempo al docker-compose.dev.yml**

Aggiungi dopo il blocco `grafana` (dopo riga 344):

```yaml
  # Grafana Tempo — trace backend (sostituisce storage Jaeger per long-term)
  tempo:
    image: grafana/tempo:2.6.1
    container_name: dev-tempo
    restart: unless-stopped
    command: ["-config.file=/etc/tempo/tempo-config.yaml"]
    volumes:
      - ./services/tempo/tempo-config.yaml:/etc/tempo/tempo-config.yaml:ro
      - tempo-dev-data:/var/tempo
    networks:
      dev-network:
        aliases:
          - tempo
```

Aggiungi volume `tempo-dev-data` nella sezione volumes:
```yaml
  tempo-dev-data:
    name: dev-tempo-data
```

- [ ] **Step 3: Aggiorna OTel Collector per esportare a Tempo**

Modifica `infrastructures/services/otel-collector/otel-collector-config.yaml`.

Aggiungi exporter Tempo dopo `otlphttp/jaeger` (dopo riga 38):
```yaml
  otlphttp/tempo:
    endpoint: http://tempo:4318
    tls:
      insecure: true
```

Aggiorna pipeline traces (riga 51):
```yaml
      exporters: [otlphttp/jaeger, otlphttp/tempo, spanmetrics, debug]
```

- [ ] **Step 4: Aggiungi Tempo datasource a Grafana**

Modifica `infrastructures/services/grafana/provisioning/datasources/datasources.yaml`.

Aggiungi dopo il datasource Jaeger:
```yaml
  - name: Tempo
    type: tempo
    access: proxy
    url: http://tempo:3200
    jsonData:
      httpMethod: GET
      tracesToLogs:
        datasourceUid: loki
        filterByTraceID: true
        filterBySpanID: true
      tracesToMetrics:
        datasourceUid: prometheus
      nodeGraph:
        enabled: true
      serviceMap:
        datasourceUid: prometheus
```

- [ ] **Step 5: Commit**

```bash
git add infrastructures/services/tempo/ \
        infrastructures/docker-compose.dev.yml \
        infrastructures/services/otel-collector/otel-collector-config.yaml \
        infrastructures/services/grafana/provisioning/datasources/datasources.yaml
git commit -m "feat(tempo): aggiungi Grafana Tempo per trace storage e service map"
```

---

## Chunk 2: Django — Migrazione Autenticazione

### Task 7: Nuovo auth backend Keycloak JWT per DRF

**Files:**
- Create: `microservices/backoffice-service/backend/backoffice/authentication.py`
- Modify: `microservices/backoffice-service/backend/requirements.txt:11` (sostituisci django-oauth-toolkit)
- Test: `microservices/backoffice-service/backend/tests/test_keycloak_auth.py`

- [ ] **Step 1: Scrivi il test per KeycloakJWTAuthentication**

File `microservices/backoffice-service/backend/tests/test_keycloak_auth.py`:

```python
"""Test per autenticazione JWT Keycloak."""
import json
import time
from unittest.mock import patch, MagicMock

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory
from rest_framework.exceptions import AuthenticationFailed

from backoffice.authentication import KeycloakJWTAuthentication


def _generate_rsa_keypair():
    """Genera coppia RSA per test."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    return private_key, public_key


def _create_jwt(private_key, claims: dict) -> str:
    """Crea un JWT firmato con RS256."""
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key-1"})


def _jwks_from_public_key(public_key) -> dict:
    """Crea JWKS dal public key."""
    from jwt import algorithms
    jwk = algorithms.RSAAlgorithm.to_jwk(public_key, as_dict=True)
    jwk["kid"] = "test-key-1"
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"
    return {"keys": [jwk]}


KEYCLOAK_SETTINGS = {
    "KEYCLOAK_URL": "http://keycloak:8080",
    "KEYCLOAK_REALM": "today-events",
    "KEYCLOAK_AUDIENCE": "account",
}


@override_settings(**KEYCLOAK_SETTINGS)
class TestKeycloakJWTAuthentication(TestCase):
    def setUp(self):
        self.private_key, self.public_key = _generate_rsa_keypair()
        self.jwks = _jwks_from_public_key(self.public_key)
        self.auth = KeycloakJWTAuthentication()
        self.factory = APIRequestFactory()

    def _valid_claims(self, **overrides):
        claims = {
            "iss": "http://keycloak:8080/realms/today-events",
            "sub": "test-user-id",
            "aud": "account",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "realm_access": {"roles": ["api-consumer"]},
            "azp": "scraper-service",
            "preferred_username": "scraper-service",
            "scope": "openid read write",
        }
        claims.update(overrides)
        return claims

    @patch("backoffice.authentication.KeycloakJWTAuthentication._get_jwks")
    def test_valid_token_authenticates(self, mock_jwks):
        mock_jwks.return_value = self.jwks
        token = _create_jwt(self.private_key, self._valid_claims())
        request = self.factory.get("/api/external/v1/staging/", HTTP_AUTHORIZATION=f"Bearer {token}")

        user, auth_info = self.auth.authenticate(request)

        self.assertIsNotNone(user)
        self.assertEqual(auth_info["azp"], "scraper-service")
        self.assertIn("api-consumer", auth_info["roles"])

    @patch("backoffice.authentication.KeycloakJWTAuthentication._get_jwks")
    def test_expired_token_raises(self, mock_jwks):
        mock_jwks.return_value = self.jwks
        token = _create_jwt(self.private_key, self._valid_claims(exp=int(time.time()) - 100))
        request = self.factory.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    @patch("backoffice.authentication.KeycloakJWTAuthentication._get_jwks")
    def test_wrong_issuer_raises(self, mock_jwks):
        mock_jwks.return_value = self.jwks
        token = _create_jwt(self.private_key, self._valid_claims(iss="http://evil.com/realms/x"))
        request = self.factory.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    def test_no_auth_header_returns_none(self):
        request = self.factory.get("/")
        result = self.auth.authenticate(request)
        self.assertIsNone(result)

    def test_non_bearer_header_returns_none(self):
        request = self.factory.get("/", HTTP_AUTHORIZATION="Basic abc123")
        result = self.auth.authenticate(request)
        self.assertIsNone(result)

    @patch("backoffice.authentication.KeycloakJWTAuthentication._get_jwks")
    def test_roles_extracted_from_realm_access(self, mock_jwks):
        mock_jwks.return_value = self.jwks
        token = _create_jwt(self.private_key, self._valid_claims(
            realm_access={"roles": ["admin", "api-consumer"]}
        ))
        request = self.factory.get("/", HTTP_AUTHORIZATION=f"Bearer {token}")

        _, auth_info = self.auth.authenticate(request)
        self.assertIn("admin", auth_info["roles"])
        self.assertIn("api-consumer", auth_info["roles"])
```

- [ ] **Step 2: Esegui test per verificare che fallisca**

Run: `cd /Users/skyweb/Sites/today_events/microservices/backoffice-service/backend && python -m pytest tests/test_keycloak_auth.py -v`
Expected: FAIL — modulo `backoffice.authentication` non trovato

- [ ] **Step 3: Implementa KeycloakJWTAuthentication**

File `microservices/backoffice-service/backend/backoffice/authentication.py`:

```python
"""
Autenticazione JWT Keycloak per Django REST Framework.

Valida i JWT emessi da Keycloak usando JWKS endpoint.
Estrae ruoli da realm_access.roles e scope dal claim scope.
"""

import logging
import time
from functools import lru_cache
from typing import Any

import jwt
import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger("keycloak.auth")

# Cache JWKS per 5 minuti
_jwks_cache: dict[str, Any] = {}
_jwks_cache_time: float = 0
JWKS_CACHE_TTL = 300  # secondi


class KeycloakJWTAuthentication(BaseAuthentication):
    """
    Autenticazione DRF via JWT Keycloak.

    Il JWT viene validato contro il JWKS endpoint di Keycloak.
    I ruoli vengono estratti dal claim `realm_access.roles`.
    """

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer "):
            return None

        token = auth_header[7:]
        if not token:
            return None

        try:
            payload = self._decode_token(token)
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed("Token scaduto")
        except jwt.InvalidIssuerError:
            raise AuthenticationFailed("Issuer non valido")
        except jwt.InvalidAudienceError:
            raise AuthenticationFailed("Audience non valido")
        except jwt.PyJWTError as e:
            raise AuthenticationFailed(f"Token non valido: {e}")

        # Estrai ruoli e scope dal payload
        roles = payload.get("realm_access", {}).get("roles", [])
        scope = payload.get("scope", "").split()
        client_id = payload.get("azp", "")
        username = payload.get("preferred_username", client_id)

        # Cerca utente Django se esiste, altrimenti usa AnonymousUser con attributi
        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # Per service account (scraper, airflow) non serve utente Django
            user = AnonymousUser()
            user.username = username  # type: ignore[attr-defined]
            user.is_authenticated = True  # type: ignore[attr-defined]

        auth_info = {
            "roles": roles,
            "scope": scope,
            "azp": client_id,
            "sub": payload.get("sub", ""),
        }

        logger.debug("JWT autenticato: client=%s roles=%s", client_id, roles)
        return (user, auth_info)

    def _decode_token(self, token: str) -> dict:
        """Decodifica e valida il JWT usando JWKS."""
        jwks = self._get_jwks()

        # Estrai kid dall'header del token
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        # Trova la chiave corrispondente nel JWKS
        public_key = None
        for key_data in jwks.get("keys", []):
            if key_data.get("kid") == kid:
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)
                break

        if public_key is None:
            # Prova a ricaricare JWKS (key rotation)
            self._invalidate_jwks_cache()
            jwks = self._get_jwks()
            for key_data in jwks.get("keys", []):
                if key_data.get("kid") == kid:
                    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)
                    break

        if public_key is None:
            raise jwt.PyJWTError(f"Chiave pubblica non trovata per kid={kid}")

        keycloak_url = getattr(settings, "KEYCLOAK_URL", "http://keycloak:8080")
        realm = getattr(settings, "KEYCLOAK_REALM", "today-events")
        issuer = f"{keycloak_url}/realms/{realm}"
        audience = getattr(settings, "KEYCLOAK_AUDIENCE", "account")

        return jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            issuer=issuer,
            audience=audience,
        )

    def _get_jwks(self) -> dict:
        """Scarica JWKS da Keycloak con cache TTL."""
        global _jwks_cache, _jwks_cache_time

        now = time.time()
        if _jwks_cache and (now - _jwks_cache_time) < JWKS_CACHE_TTL:
            return _jwks_cache

        keycloak_url = getattr(settings, "KEYCLOAK_URL", "http://keycloak:8080")
        realm = getattr(settings, "KEYCLOAK_REALM", "today-events")
        jwks_url = f"{keycloak_url}/realms/{realm}/protocol/openid-connect/certs"

        try:
            response = requests.get(jwks_url, timeout=10)
            response.raise_for_status()
            _jwks_cache = response.json()
            _jwks_cache_time = now
            return _jwks_cache
        except requests.RequestException as e:
            if _jwks_cache:
                logger.warning("Errore scaricamento JWKS, uso cache: %s", e)
                return _jwks_cache
            raise AuthenticationFailed(f"Impossibile scaricare JWKS: {e}")

    def _invalidate_jwks_cache(self):
        """Invalida la cache JWKS per forzare il rinnovo."""
        global _jwks_cache_time
        _jwks_cache_time = 0


class HasKeycloakRole:
    """
    Permission class per verificare ruoli Keycloak.

    Uso: permission_classes = [HasKeycloakRole]
    Nella view: required_roles = ['admin'] o required_roles = ['api-consumer']
    """

    def has_permission(self, request, view) -> bool:
        if not hasattr(request, "auth") or not isinstance(request.auth, dict):
            return False

        required_roles = getattr(view, "required_roles", [])
        if not required_roles:
            return True

        user_roles = request.auth.get("roles", [])
        return any(role in user_roles for role in required_roles)


class HasKeycloakScope:
    """
    Permission class per verificare scope Keycloak (equivalente a TokenHasScope).

    Uso: permission_classes = [HasKeycloakScope]
    Nella view: required_scopes = ['read'] o required_scopes = ['write']
    """

    def has_permission(self, request, view) -> bool:
        if not hasattr(request, "auth") or not isinstance(request.auth, dict):
            return False

        required_scopes = getattr(view, "required_scopes", [])
        if not required_scopes:
            return True

        user_scopes = request.auth.get("scope", [])
        return all(scope in user_scopes for scope in required_scopes)
```

- [ ] **Step 4: Aggiorna requirements.txt**

Sostituisci riga 11 `django-oauth-toolkit==2.3.0` con:
```
PyJWT[crypto]==2.9.0
```

- [ ] **Step 5: Esegui test**

Run: `cd /Users/skyweb/Sites/today_events/microservices/backoffice-service/backend && python -m pytest tests/test_keycloak_auth.py -v`
Expected: PASS (tutti i test)

- [ ] **Step 6: Commit**

```bash
git add microservices/backoffice-service/backend/backoffice/authentication.py \
        microservices/backoffice-service/backend/tests/test_keycloak_auth.py \
        microservices/backoffice-service/backend/requirements.txt
git commit -m "feat(auth): autenticazione JWT Keycloak per DRF con test"
```

---

### Task 8: Aggiorna Django Settings e URL

**Files:**
- Modify: `microservices/backoffice-service/backend/backoffice/settings.py:38,146-177,196-268`
- Modify: `microservices/backoffice-service/backend/backoffice/urls.py:51,60`

- [ ] **Step 1: Aggiorna INSTALLED_APPS — rimuovi oauth2_provider**

In `settings.py`, rimuovi riga 38:
```python
    'oauth2_provider',
```

- [ ] **Step 2: Aggiorna REST_FRAMEWORK authentication classes**

Sostituisci righe 150-152:
```python
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'oauth2_provider.contrib.rest_framework.OAuth2Authentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
```
con:
```python
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'backoffice.authentication.KeycloakJWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
```

- [ ] **Step 3: Rimuovi OAUTH2_PROVIDER config e aggiungi KEYCLOAK settings**

Sostituisci righe 168-177:
```python
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
```
con:
```python
# Keycloak (Identity Provider)
KEYCLOAK_URL = os.environ.get('KEYCLOAK_URL', 'http://keycloak:8080')
KEYCLOAK_REALM = os.environ.get('KEYCLOAK_REALM', 'today-events')
KEYCLOAK_AUDIENCE = os.environ.get('KEYCLOAK_AUDIENCE', 'account')
```

- [ ] **Step 4: Aggiorna SPECTACULAR_SETTINGS per Keycloak OIDC**

Sostituisci la sezione `OAUTH2_FLOWS` e `OAUTH2_TOKEN_URL` e `COMPONENTS.securitySchemes` (righe 236-258):
```python
    'OAUTH2_FLOWS': ['clientCredentials'],
    'OAUTH2_TOKEN_URL': '/oauth/token/',
    'COMPONENTS': {
        'securitySchemes': {
            'OAuth2': {
                'type': 'oauth2',
                'flows': {
                    'clientCredentials': {
                        'tokenUrl': '/oauth/token/',
```
con:
```python
    'OAUTH2_FLOWS': ['clientCredentials'],
    'OAUTH2_TOKEN_URL': f'{os.environ.get("KEYCLOAK_URL", "http://keycloak:8080")}/realms/{os.environ.get("KEYCLOAK_REALM", "today-events")}/protocol/openid-connect/token',
    'COMPONENTS': {
        'securitySchemes': {
            'OAuth2': {
                'type': 'oauth2',
                'flows': {
                    'clientCredentials': {
                        'tokenUrl': f'{os.environ.get("KEYCLOAK_URL", "http://keycloak:8080")}/realms/{os.environ.get("KEYCLOAK_REALM", "today-events")}/protocol/openid-connect/token',
```

Aggiorna anche la descrizione SPECTACULAR_SETTINGS (righe 210-214):
```
1. Richiedi le credenziali (Client ID e Client Secret) all'amministratore
2. Ottieni un access token: `POST /oauth/token/` con `grant_type=client_credentials`
3. Usa il token: `Authorization: Bearer <access_token>`
```
con:
```
1. Richiedi le credenziali (Client ID e Client Secret) dall'admin Keycloak
2. Ottieni un access token: `POST {KEYCLOAK_URL}/realms/today-events/protocol/openid-connect/token` con `grant_type=client_credentials`
3. Usa il token: `Authorization: Bearer <access_token>`
```

- [ ] **Step 5: Rimuovi URL OAuth2 da urls.py**

Rimuovi riga 51:
```python
    path('oauth/', include('oauth2_provider.urls', namespace='oauth2_provider')),
```

Aggiorna il catch-all SPA riga 60 — rimuovi `oauth` dal pattern:
```python
    re_path(r'^(?!admin|api|static|media|docs|ckeditor5|metrics).*$', serve_frontend),
```

- [ ] **Step 6: Aggiorna settings.py — aggiungi KEYCLOAK_URL all'env del backoffice in docker-compose**

In `infrastructures/docker-compose.dev.yml`, nel blocco `backoffice` (dopo riga 137), aggiungi:
```yaml
      KEYCLOAK_URL: http://keycloak:8080
      KEYCLOAK_REALM: today-events
      KEYCLOAK_AUDIENCE: account
```

Stesse variabili per `backoffice-celery-worker` (dopo riga 179).

- [ ] **Step 7: Esegui test suite completa**

Run: `cd /Users/skyweb/Sites/today_events/microservices/backoffice-service/backend && python -m pytest -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add microservices/backoffice-service/backend/backoffice/settings.py \
        microservices/backoffice-service/backend/backoffice/urls.py \
        infrastructures/docker-compose.dev.yml
git commit -m "refactor(auth): migra da django-oauth-toolkit a Keycloak JWT"
```

---

### Task 9: Aggiorna Views — sostituisci TokenHasScope con HasKeycloakScope

**Files:**
- Modify: `microservices/backoffice-service/backend/events/views.py:6,417-422`

- [ ] **Step 1: Aggiorna import**

Sostituisci riga 6:
```python
from oauth2_provider.contrib.rest_framework import TokenHasReadWriteScope, TokenHasScope
```
con:
```python
from backoffice.authentication import HasKeycloakScope
```

- [ ] **Step 2: Aggiorna ExternalStagingEventViewSet.get_permissions()**

Cerca il metodo `get_permissions` in `ExternalStagingEventViewSet` e sostituisci i riferimenti a `TokenHasScope` con `HasKeycloakScope`:

```python
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            self.required_scopes = ['read']
        else:
            self.required_scopes = ['write']
        return [HasKeycloakScope()]
```

- [ ] **Step 3: Esegui test**

Run: `cd /Users/skyweb/Sites/today_events/microservices/backoffice-service/backend && python -m pytest tests/ -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add microservices/backoffice-service/backend/events/views.py
git commit -m "refactor(views): usa HasKeycloakScope al posto di TokenHasScope"
```

---

### Task 10: Aggiorna Middleware SSO per Keycloak

**Files:**
- Modify: `microservices/backoffice-service/backend/backoffice/middleware.py:22-74`

- [ ] **Step 1: Aggiorna OAuth2ProxyAdminMiddleware per Keycloak**

Il middleware legge `X-Auth-Request-Email` da APISIX (che lo ottiene dal plugin openid-connect).
La logica resta identica — solo docstring e commenti cambiano.

Aggiorna la docstring della classe (righe 22-35):
```python
class KeycloakAdminMiddleware:
    """
    SSO trasparente per Django Admin via APISIX + Keycloak.

    Flusso:
      1. APISIX autentica la richiesta via plugin openid-connect → Keycloak
      2. Keycloak valida la sessione/token e restituisce i claim
      3. APISIX imposta X-Auth-Request-Email nell'header della richiesta
      4. Questo middleware legge l'email e fa il login automatico

    Attivo solo su /admin/. Le API (/api/) usano JWT diretto.
    Non crea utenti automaticamente: l'utente Django deve esistere con la stessa email
    e avere is_staff=True. In caso contrario restituisce 403 con istruzioni.
    """
```

- [ ] **Step 2: Aggiorna settings.py MIDDLEWARE reference**

In `settings.py` riga 63, aggiorna il path del middleware se rinominato:
```python
    'backoffice.middleware.KeycloakAdminMiddleware',
```

- [ ] **Step 3: Commit**

```bash
git add microservices/backoffice-service/backend/backoffice/middleware.py \
        microservices/backoffice-service/backend/backoffice/settings.py
git commit -m "refactor(middleware): rinomina OAuth2ProxyAdminMiddleware in KeycloakAdminMiddleware"
```

---

## Chunk 3: Scraper e Airflow — Token Keycloak

### Task 11: Aggiorna Scrapy Pipeline per Keycloak

**Files:**
- Modify: `microservices/scraping-service/src/pipelines.py:361-392`

- [ ] **Step 1: Aggiorna _get_access_token() per usare Keycloak token endpoint**

Sostituisci righe 367-376:
```python
        token_url = f"{self.base_url}/oauth/token/"

        try:
            response = self.session.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "read write",
                },
```
con:
```python
        # Token endpoint Keycloak — usa env var dedicata o costruisci dall'URL base
        keycloak_token_url = self.settings.get("KEYCLOAK_TOKEN_URL") or os.environ.get(
            "KEYCLOAK_TOKEN_URL",
            "http://keycloak:8080/realms/today-events/protocol/openid-connect/token"
        )

        try:
            response = self.session.post(
                keycloak_token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "openid read write",
                },
```

- [ ] **Step 2: Commit**

```bash
git add microservices/scraping-service/src/pipelines.py
git commit -m "feat(scraper): usa Keycloak token endpoint per autenticazione API"
```

---

### Task 12: Aggiorna Airflow DAG scrape_eventi

**Files:**
- Modify: `infrastructures/services/airflow/dags/scrape_events.py:56-69`

- [ ] **Step 1: Aggiungi KEYCLOAK_TOKEN_URL all'env dei container Scrapy**

In `get_scrapy_env()` (righe 56-69), aggiungi:
```python
        'KEYCLOAK_TOKEN_URL': Variable.get(
            'KEYCLOAK_TOKEN_URL',
            default_var=os.getenv(
                'KEYCLOAK_TOKEN_URL',
                'http://keycloak:8080/realms/today-events/protocol/openid-connect/token'
            )
        ),
```

- [ ] **Step 2: Commit**

```bash
git add infrastructures/services/airflow/dags/scrape_events.py
git commit -m "feat(airflow): passa KEYCLOAK_TOKEN_URL ai container Scrapy"
```

---

### Task 13: Aggiorna Airflow DAG scrape_comuni

**Files:**
- Modify: `infrastructures/services/airflow/dags/scrape_comuni.py:50-65`

- [ ] **Step 1: Aggiorna get_oauth_token() per Keycloak**

Sostituisci righe 50-65:
```python
def get_oauth_token():
    """Ottiene token OAuth2 per chiamare l'API di ingestion"""
    client_id = Variable.get('API_CLIENT_ID', default_var=os.getenv('API_CLIENT_ID', ''))
    client_secret = Variable.get('API_CLIENT_SECRET', default_var=os.getenv('API_CLIENT_SECRET', ''))

    resp = requests.post(
        f'{API_BASE_URL}/oauth/token/',
        data={
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()['access_token']
```
con:
```python
def get_oauth_token():
    """Ottiene token JWT da Keycloak per chiamare l'API di ingestion"""
    client_id = Variable.get('API_CLIENT_ID', default_var=os.getenv('API_CLIENT_ID', ''))
    client_secret = Variable.get('API_CLIENT_SECRET', default_var=os.getenv('API_CLIENT_SECRET', ''))
    token_url = Variable.get(
        'KEYCLOAK_TOKEN_URL',
        default_var=os.getenv(
            'KEYCLOAK_TOKEN_URL',
            'http://keycloak:8080/realms/today-events/protocol/openid-connect/token'
        )
    )

    resp = requests.post(
        token_url,
        data={
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
            'scope': 'openid read write',
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()['access_token']
```

- [ ] **Step 2: Commit**

```bash
git add infrastructures/services/airflow/dags/scrape_comuni.py
git commit -m "feat(airflow): usa Keycloak token endpoint per DAG comuni"
```

---

## Chunk 4: Produzione — Kubernetes (OKE)

### Task 14: K8s — Keycloak Deployment

**Files:**
- Create: `infrastructures/OCI/k8s/keycloak/keycloak-values.yml`
- Create: `infrastructures/OCI/k8s/keycloak/keycloak-realm-configmap.yml`
- Create: `infrastructures/OCI/k8s/keycloak/keycloak-ingressroute.yml`
- Create: `infrastructures/OCI/k8s/keycloak/kustomization.yml`

- [ ] **Step 1: Crea keycloak-values.yml (Helm Bitnami)**

```yaml
# Keycloak Helm values — Bitnami chart
# https://github.com/bitnami/charts/tree/main/bitnami/keycloak

image:
  registry: quay.io
  repository: keycloak/keycloak
  tag: "26.0"

auth:
  adminUser: admin
  existingSecret: keycloak-secret
  passwordSecretKey: admin-password

production: true
proxy: edge
httpRelativePath: "/"

extraEnvVars:
  - name: KC_HEALTH_ENABLED
    value: "true"
  - name: KC_METRICS_ENABLED
    value: "true"
  - name: KC_TRACING_ENABLED
    value: "true"
  - name: KC_TRACING_ENDPOINT
    value: "http://otel-collector.monitoring.svc:4317"

postgresql:
  enabled: false

externalDatabase:
  host: postgres.database.svc
  port: 5432
  database: keycloak
  user: keycloak
  existingSecret: keycloak-secret
  existingSecretPasswordKey: db-password

service:
  type: ClusterIP
  ports:
    http: 8080

resources:
  requests:
    cpu: 200m
    memory: 512Mi
  limits:
    cpu: 1000m
    memory: 1Gi

nodeSelector:
  workload: heavy

extraVolumes:
  - name: realm-config
    configMap:
      name: keycloak-realm-config

extraVolumeMounts:
  - name: realm-config
    mountPath: /opt/keycloak/data/import
    readOnly: true
```

- [ ] **Step 2: Crea ConfigMap per il realm template**

File `infrastructures/OCI/k8s/keycloak/keycloak-realm-configmap.yml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: keycloak-realm-config
  namespace: apps
data:
  realm-today-events.json: |
    # contenuto di infrastructures/services/keycloak/realm-today-events.json
    # (copia il JSON del Task 1)
```

- [ ] **Step 3: Crea IngressRoute**

File `infrastructures/OCI/k8s/keycloak/keycloak-ingressroute.yml`:

```yaml
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: keycloak
  namespace: apps
spec:
  entryPoints:
    - websecure
  routes:
    - match: Host(`auth.oci.santocaruso.eu`)
      kind: Rule
      services:
        - name: keycloak
          port: 8080
  tls:
    certResolver: letsencrypt
```

- [ ] **Step 4: Crea kustomization.yml**

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - keycloak-realm-configmap.yml
  - keycloak-ingressroute.yml
```

- [ ] **Step 5: Commit**

```bash
git add infrastructures/OCI/k8s/keycloak/
git commit -m "feat(k8s): deployment Keycloak con Helm, realm config e IngressRoute"
```

---

### Task 15: K8s — APISIX Deployment con CRD

**Files:**
- Create: `infrastructures/OCI/k8s/apisix/apisix-values.yml`
- Create: `infrastructures/OCI/k8s/apisix/apisix-routes.yml`
- Create: `infrastructures/OCI/k8s/apisix/apisix-ingressroute.yml`
- Create: `infrastructures/OCI/k8s/apisix/kustomization.yml`

- [ ] **Step 1: Crea apisix-values.yml (Helm chart APISIX)**

```yaml
# APISIX Helm values
# https://github.com/apache/apisix-helm-chart

apisix:
  image:
    repository: apache/apisix
    tag: "3.11-debian"

  kind: Deployment
  replicaCount: 1

  nodeSelector:
    workload: heavy

  resources:
    requests:
      cpu: 100m
      memory: 256Mi
    limits:
      cpu: 500m
      memory: 512Mi

gateway:
  type: ClusterIP
  http:
    enabled: true
    servicePort: 9080
    containerPort: 9080

admin:
  enabled: true
  type: ClusterIP
  port: 9180
  credentials:
    admin: apisix-admin-key
    viewer: apisix-viewer-key

etcd:
  enabled: true
  replicaCount: 1
  persistence:
    size: 2Gi
  nodeSelector:
    workload: light

dashboard:
  enabled: true
  image:
    repository: apache/apisix-dashboard
    tag: "3.0-alpine"

ingress-controller:
  enabled: true
  config:
    apisix:
      serviceNamespace: apps
      adminKey: apisix-admin-key

pluginAttrs:
  prometheus:
    export_addr:
      ip: 0.0.0.0
      port: 9091
  opentelemetry:
    resource:
      service.name: apisix-gateway
    collector:
      address: otel-collector.monitoring.svc:4317
      request_timeout: 3
```

- [ ] **Step 2: Crea ApisixRoute CRD**

File `infrastructures/OCI/k8s/apisix/apisix-routes.yml`:

```yaml
# Route API esterna — autenticazione JWT Keycloak
apiVersion: apisix.apache.org/v2
kind: ApisixRoute
metadata:
  name: api-external
  namespace: apps
spec:
  http:
    - name: api-external
      match:
        hosts:
          - api.oci.santocaruso.eu
        paths:
          - /api/external/*
      backends:
        - serviceName: backoffice
          servicePort: 8000
      plugins:
        - name: openid-connect
          enable: true
          config:
            discovery: http://keycloak.apps.svc:8080/realms/today-events/.well-known/openid-configuration
            bearer_only: true
            realm: today-events
            token_signing_alg_values_expected: RS256
        - name: limit-count
          enable: true
          config:
            count: 60
            time_window: 60
            key_type: consumer_name
            rejected_code: 429
        - name: cors
          enable: true
          config:
            allow_origins: "https://events.oci.santocaruso.eu,https://gateway.oci.santocaruso.eu"
            allow_methods: "GET,POST,PUT,DELETE,OPTIONS"
            allow_headers: "Accept,Content-Type,Authorization"
            allow_credential: true
            max_age: 3600
        - name: opentelemetry
          enable: true
        - name: prometheus
          enable: true
---
# Route API pubblica — nessuna autenticazione
apiVersion: apisix.apache.org/v2
kind: ApisixRoute
metadata:
  name: api-public
  namespace: apps
spec:
  http:
    - name: api-public
      match:
        hosts:
          - api.oci.santocaruso.eu
        paths:
          - /api/public/*
      backends:
        - serviceName: backoffice
          servicePort: 8000
      plugins:
        - name: cors
          enable: true
        - name: opentelemetry
          enable: true
---
# Route Gateway Admin — SSO Keycloak (browser)
apiVersion: apisix.apache.org/v2
kind: ApisixRoute
metadata:
  name: gateway-admin
  namespace: apps
spec:
  http:
    - name: gateway-admin
      match:
        hosts:
          - gateway.oci.santocaruso.eu
        paths:
          - /admin/*
      backends:
        - serviceName: backoffice
          servicePort: 8000
      plugins:
        - name: openid-connect
          enable: true
          config:
            discovery: http://keycloak.apps.svc:8080/realms/today-events/.well-known/openid-configuration
            client_id: backoffice-admin
            client_secret: "${KEYCLOAK_BACKOFFICE_SECRET}"
            redirect_uri: https://gateway.oci.santocaruso.eu/callback
            scope: openid profile email
            session:
              secret: apisix-session-secret
            set_id_token_header: false
            set_access_token_header: true
            set_userinfo_header: true
            unauth_action: redirect
        - name: opentelemetry
          enable: true
---
# Route Gateway API — SSO Keycloak (browser)
apiVersion: apisix.apache.org/v2
kind: ApisixRoute
metadata:
  name: gateway-api
  namespace: apps
spec:
  http:
    - name: gateway-api
      match:
        hosts:
          - gateway.oci.santocaruso.eu
        paths:
          - /api/*
      backends:
        - serviceName: backoffice
          servicePort: 8000
      plugins:
        - name: openid-connect
          enable: true
          config:
            discovery: http://keycloak.apps.svc:8080/realms/today-events/.well-known/openid-configuration
            client_id: backoffice-admin
            client_secret: "${KEYCLOAK_BACKOFFICE_SECRET}"
            redirect_uri: https://gateway.oci.santocaruso.eu/callback
            scope: openid profile email
            session:
              secret: apisix-session-secret
            unauth_action: redirect
        - name: opentelemetry
          enable: true
---
# Route Static — nessuna autenticazione
apiVersion: apisix.apache.org/v2
kind: ApisixRoute
metadata:
  name: gateway-static
  namespace: apps
spec:
  http:
    - name: gateway-static
      match:
        hosts:
          - gateway.oci.santocaruso.eu
        paths:
          - /static/*
      backends:
        - serviceName: backoffice
          servicePort: 8000
```

- [ ] **Step 3: Crea IngressRoute Traefik → APISIX**

File `infrastructures/OCI/k8s/apisix/apisix-ingressroute.yml`:

```yaml
# API Gateway (Traefik → APISIX)
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: apisix-api
  namespace: apps
spec:
  entryPoints:
    - websecure
  routes:
    - match: Host(`api.oci.santocaruso.eu`)
      kind: Rule
      services:
        - name: apisix-gateway
          port: 9080
  tls:
    certResolver: letsencrypt
---
# Gateway Browser (Traefik → APISIX)
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: apisix-gateway
  namespace: apps
spec:
  entryPoints:
    - websecure
  routes:
    - match: Host(`gateway.oci.santocaruso.eu`)
      kind: Rule
      services:
        - name: apisix-gateway
          port: 9080
  tls:
    certResolver: letsencrypt
---
# APISIX Dashboard
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: apisix-dashboard
  namespace: apps
spec:
  entryPoints:
    - websecure
  routes:
    - match: Host(`apisix.oci.santocaruso.eu`)
      kind: Rule
      middlewares:
        - name: keycloak-auth
          namespace: traefik
      services:
        - name: apisix-dashboard
          port: 9000
  tls:
    certResolver: letsencrypt
```

- [ ] **Step 4: Crea kustomization.yml**

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - apisix-routes.yml
  - apisix-ingressroute.yml
```

- [ ] **Step 5: Commit**

```bash
git add infrastructures/OCI/k8s/apisix/
git commit -m "feat(k8s): APISIX deployment con CRD routes e Traefik IngressRoute"
```

---

### Task 16: K8s — Cleanup Kong e OAuth2 Proxy

**Files:**
- Delete: `infrastructures/OCI/k8s/kong/` (tutta la directory)
- Delete: `infrastructures/OCI/k8s/oauth/` (tutta la directory)
- Delete: `infrastructures/OCI/ansible/playbooks/kong-setup.yml`
- Modify: `infrastructures/OCI/ansible/vars/oke.yml.example` (rimuovi kong vars, aggiungi keycloak/apisix)
- Modify: `infrastructures/OCI/ansible/vars/oke-vault.yml.example` (rimuovi kong secrets, aggiungi keycloak)
- Modify: `infrastructures/OCI/k8s/monitoring/prometheus-values.yml` (kong → apisix target)

- [ ] **Step 1: Rimuovi directory kong e oauth**

```bash
git rm -r infrastructures/OCI/k8s/kong/
git rm -r infrastructures/OCI/k8s/oauth/
git rm infrastructures/OCI/ansible/playbooks/kong-setup.yml
```

- [ ] **Step 2: Aggiorna oke.yml.example**

Rimuovi le variabili Kong (circa righe 80-90):
```yaml
install_kong: true
kong_sso_email_map: ...
kong_rate_limit_minute: 60
kong_rate_limit_hour: 1000
```

Aggiungi variabili Keycloak/APISIX:
```yaml
# Keycloak
install_keycloak: true
keycloak_realm: today-events
keycloak_google_client_id: "YOUR_GOOGLE_CLIENT_ID"

# APISIX
install_apisix: true
apisix_rate_limit_minute: 60
apisix_rate_limit_hour: 1000
```

- [ ] **Step 3: Aggiorna oke-vault.yml.example**

Rimuovi Kong secrets (circa righe 42-47):
```yaml
kong_postgres_password: "CHANGE_ME"
kong_apikey_scraper: "CHANGE_ME"
kong_apikey_airflow: "CHANGE_ME"
```

Aggiungi Keycloak secrets:
```yaml
# Keycloak
keycloak_admin_password: "CHANGE_ME"
keycloak_db_password: "CHANGE_ME"
keycloak_backoffice_client_secret: "CHANGE_ME"
keycloak_scraper_client_secret: "CHANGE_ME"
keycloak_airflow_client_secret: "CHANGE_ME"
keycloak_google_client_secret: "CHANGE_ME"
```

Rimuovi OAuth2 Proxy secrets (circa righe 53-56).

- [ ] **Step 4: Aggiorna prometheus-values.yml — kong → apisix**

Cerca il blocco Kong metrics (circa riga 76-79):
```yaml
        - job_name: kong
          static_configs:
            - targets:
                - "kong-kong-status.apps.svc:8100"
```

Sostituisci con:
```yaml
        - job_name: apisix
          static_configs:
            - targets:
                - "apisix-gateway.apps.svc:9091"
        - job_name: keycloak
          metrics_path: /metrics
          static_configs:
            - targets:
                - "keycloak.apps.svc:8080"
```

- [ ] **Step 5: Commit**

```bash
git add -A infrastructures/OCI/
git commit -m "refactor(k8s): rimuovi Kong/OAuth2Proxy, aggiorna vars per APISIX+Keycloak"
```

---

### Task 17: Ansible — Nuovo playbook setup

**Files:**
- Create: `infrastructures/OCI/ansible/playbooks/apisix-keycloak-setup.yml`

- [ ] **Step 1: Crea il playbook**

File `infrastructures/OCI/ansible/playbooks/apisix-keycloak-setup.yml`:

```yaml
---
# Playbook: Setup APISIX API Gateway + Keycloak Identity Provider
# Sostituisce: kong-setup.yml
#
# Prerequisiti: post-cluster-setup.yml completato
# Esecuzione: ansible-playbook playbooks/apisix-keycloak-setup.yml --ask-vault-pass

- name: Setup APISIX + Keycloak
  hosts: localhost
  connection: local
  gather_facts: false

  vars_files:
    - ../vars/oke.yml
    - ../vars/oke-vault.yml

  vars:
    keycloak_k8s_dir: "{{ playbook_dir }}/../../k8s/keycloak"
    apisix_k8s_dir: "{{ playbook_dir }}/../../k8s/apisix"

  tasks:
    # ─── Prerequisiti ───────────────────────────────────────────────
    - name: Verifica prerequisiti
      block:
        - name: Check kubectl
          command: kubectl cluster-info
          changed_when: false

        - name: Check helm
          command: helm version --short
          changed_when: false

    # ─── Database Keycloak ──────────────────────────────────────────
    - name: Crea database e utente Keycloak
      block:
        - name: Crea utente keycloak in PostgreSQL
          kubernetes.core.k8s_exec:
            namespace: database
            pod: postgres-0
            command: >
              psql -U postgres -c
              "DO $$ BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'keycloak') THEN
                  CREATE ROLE keycloak WITH LOGIN PASSWORD '{{ keycloak_db_password }}';
                END IF;
              END $$;"
          changed_when: false

        - name: Crea database keycloak
          kubernetes.core.k8s_exec:
            namespace: database
            pod: postgres-0
            command: >
              psql -U postgres -c
              "SELECT 'CREATE DATABASE keycloak OWNER keycloak'
               WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'keycloak') \gexec"
          changed_when: false

    # ─── Secret Keycloak ────────────────────────────────────────────
    - name: Crea secret Keycloak
      kubernetes.core.k8s:
        state: present
        definition:
          apiVersion: v1
          kind: Secret
          metadata:
            name: keycloak-secret
            namespace: apps
          type: Opaque
          stringData:
            admin-password: "{{ keycloak_admin_password }}"
            db-password: "{{ keycloak_db_password }}"

    # ─── Deploy Keycloak ────────────────────────────────────────────
    - name: Deploy Keycloak via Helm
      block:
        - name: Aggiungi repo Bitnami
          command: helm repo add bitnami https://charts.bitnami.com/bitnami
          changed_when: false
          failed_when: false

        - name: Aggiorna repo Helm
          command: helm repo update
          changed_when: false

        - name: Installa Keycloak
          command: >
            helm upgrade --install keycloak bitnami/keycloak
            --namespace apps
            --values {{ keycloak_k8s_dir }}/keycloak-values.yml
            --wait --timeout 300s

        - name: Applica manifest Keycloak (IngressRoute, ConfigMap)
          command: kubectl apply -k {{ keycloak_k8s_dir }}

    # ─── Deploy APISIX ──────────────────────────────────────────────
    - name: Deploy APISIX via Helm
      block:
        - name: Aggiungi repo APISIX
          command: helm repo add apisix https://charts.apiseven.com
          changed_when: false
          failed_when: false

        - name: Installa APISIX con Ingress Controller
          command: >
            helm upgrade --install apisix apisix/apisix
            --namespace apps
            --values {{ apisix_k8s_dir }}/apisix-values.yml
            --wait --timeout 300s

        - name: Applica CRD routes e IngressRoute
          command: kubectl apply -k {{ apisix_k8s_dir }}

    # ─── Verifica ───────────────────────────────────────────────────
    - name: Verifica deployment
      block:
        - name: Verifica pods Keycloak
          command: kubectl get pods -n apps -l app.kubernetes.io/name=keycloak -o wide
          register: keycloak_pods
          changed_when: false

        - name: Verifica pods APISIX
          command: kubectl get pods -n apps -l app.kubernetes.io/name=apisix -o wide
          register: apisix_pods
          changed_when: false

        - name: Output stato
          debug:
            msg: |
              === APISIX + Keycloak Setup Completato ===

              Keycloak pods:
              {{ keycloak_pods.stdout }}

              APISIX pods:
              {{ apisix_pods.stdout }}

              Endpoint:
                Keycloak:  https://auth.{{ base_domain }}
                API:       https://api.{{ base_domain }}
                Gateway:   https://gateway.{{ base_domain }}
                Dashboard: https://apisix.{{ base_domain }}
```

- [ ] **Step 2: Commit**

```bash
git add infrastructures/OCI/ansible/playbooks/apisix-keycloak-setup.yml
git commit -m "feat(ansible): playbook setup APISIX + Keycloak per OKE"
```

---

## Chunk 5: Grafana Dashboard e Documentazione

### Task 18: Grafana Dashboard preconfigurate

**Files:**
- Create: `infrastructures/services/grafana/provisioning/dashboards/dashboards.yaml`
- Create: `infrastructures/services/grafana/dashboards/apisix.json`
- Create: `infrastructures/services/grafana/dashboards/keycloak.json`

- [ ] **Step 1: Crea dashboard provisioning config**

File `infrastructures/services/grafana/provisioning/dashboards/dashboards.yaml`:

```yaml
apiVersion: 1

providers:
  - name: default
    orgId: 1
    folder: ""
    type: file
    disableDeletion: false
    editable: true
    options:
      path: /var/lib/grafana/dashboards
      foldersFromFilesStructure: false
```

- [ ] **Step 2: Aggiungi volume dashboards al docker-compose**

Nel servizio `grafana` di `docker-compose.dev.yml`, aggiungi volume:
```yaml
      - ./services/grafana/dashboards:/var/lib/grafana/dashboards:ro
```

- [ ] **Step 3: Crea dashboard APISIX (placeholder)**

File `infrastructures/services/grafana/dashboards/apisix.json`:

Usa il dashboard ufficiale APISIX Grafana (ID: 11719) come base. Crea un JSON minimale:

```json
{
  "annotations": {"list": []},
  "title": "APISIX Gateway",
  "uid": "apisix-gateway",
  "panels": [
    {
      "title": "Request Rate",
      "type": "timeseries",
      "datasource": "Prometheus",
      "targets": [{"expr": "sum(rate(apisix_http_status{code=~\".*\"}[5m]))", "legendFormat": "{{code}}"}],
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0}
    },
    {
      "title": "Latency P95",
      "type": "timeseries",
      "datasource": "Prometheus",
      "targets": [{"expr": "histogram_quantile(0.95, sum(rate(apisix_http_latency_bucket[5m])) by (le, route))", "legendFormat": "{{route}}"}],
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0}
    },
    {
      "title": "Active Connections",
      "type": "stat",
      "datasource": "Prometheus",
      "targets": [{"expr": "apisix_nginx_http_current_connections{state=\"active\"}"}],
      "gridPos": {"h": 4, "w": 6, "x": 0, "y": 8}
    }
  ],
  "schemaVersion": 39,
  "version": 1
}
```

- [ ] **Step 4: Crea dashboard Keycloak (placeholder)**

File `infrastructures/services/grafana/dashboards/keycloak.json`:

```json
{
  "annotations": {"list": []},
  "title": "Keycloak Identity Provider",
  "uid": "keycloak-idp",
  "panels": [
    {
      "title": "Login Events",
      "type": "timeseries",
      "datasource": "Prometheus",
      "targets": [{"expr": "sum(rate(keycloak_login_total[5m])) by (realm, provider)", "legendFormat": "{{realm}}/{{provider}}"}],
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0}
    },
    {
      "title": "Token Issued",
      "type": "timeseries",
      "datasource": "Prometheus",
      "targets": [{"expr": "sum(rate(keycloak_token_total[5m])) by (client_id)", "legendFormat": "{{client_id}}"}],
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0}
    },
    {
      "title": "Failed Logins",
      "type": "stat",
      "datasource": "Prometheus",
      "targets": [{"expr": "sum(rate(keycloak_failed_login_total[5m]))"}],
      "gridPos": {"h": 4, "w": 6, "x": 0, "y": 8}
    }
  ],
  "schemaVersion": 39,
  "version": 1
}
```

- [ ] **Step 5: Commit**

```bash
git add infrastructures/services/grafana/
git commit -m "feat(grafana): dashboard APISIX e Keycloak con provisioning automatico"
```

---

### Task 19: Aggiorna documentazione architettura

**Files:**
- Modify: `docs/infrastructure_Today_Events.md` (aggiorna riferimenti Kong → APISIX + Keycloak)

- [ ] **Step 1: Aggiorna la documentazione infrastrutturale**

Cerca tutti i riferimenti a "Kong" nel file e sostituiscili con la nuova architettura APISIX + Keycloak. Aggiorna i diagrammi e le tabelle dei servizi.

- [ ] **Step 2: Commit**

```bash
git add docs/infrastructure_Today_Events.md
git commit -m "docs: aggiorna architettura da Kong a APISIX + Keycloak"
```

---

### Task 20: Test end-to-end e verifica

- [ ] **Step 1: Avvia lo stack dev**

```bash
cd /Users/skyweb/Sites/today_events/infrastructures
make up-core
make up-devtools
make up-app
make up-observability
```

- [ ] **Step 2: Verifica Keycloak**

```bash
curl -s http://localhost:8080/realms/today-events/.well-known/openid-configuration | python3 -m json.tool
```
Expected: JSON con endpoint token, jwks_uri, etc.

- [ ] **Step 3: Ottieni token da Keycloak**

```bash
curl -s -X POST http://localhost:8080/realms/today-events/protocol/openid-connect/token \
  -d "grant_type=client_credentials" \
  -d "client_id=scraper-service" \
  -d "client_secret=CHANGE_ME_SCRAPER_SECRET" \
  -d "scope=openid read write" | python3 -m json.tool
```
Expected: JSON con `access_token` (JWT)

- [ ] **Step 4: Chiama API con token JWT**

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/realms/today-events/protocol/openid-connect/token \
  -d "grant_type=client_credentials" \
  -d "client_id=scraper-service" \
  -d "client_secret=CHANGE_ME_SCRAPER_SECRET" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s http://localhost:8000/api/external/v1/staging/ \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```
Expected: risposta API 200 OK

- [ ] **Step 5: Verifica APISIX Dashboard**

Apri `https://apisix.127.0.0.1.nip.io` — login con admin/admin

- [ ] **Step 6: Verifica trace in Grafana**

Apri `https://grafana.127.0.0.1.nip.io` → Explore → Tempo → cerca trace recenti

- [ ] **Step 7: Commit finale**

```bash
git add -A
git commit -m "feat: migrazione completa Kong → APISIX + Keycloak"
```
