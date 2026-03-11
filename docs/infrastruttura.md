# Infrastruttura Today Events — Documentazione Tecnica

## Panoramica

```
Internet
   │
   ▼
Traefik (TLS termination, edge routing)
   │
   ▼
APISIX 3.11 (API Gateway — autenticazione, rate-limit, CORS, tracing)
   │         │
   │         └──► Keycloak 26 (IdP — SSO, token, JWKS)
   │                  │
   │                  └──► PostgreSQL (db: keycloak)
   ▼
Django Backoffice (PyJWT, SessionAuth)
   │         │
   │         └──► PostgreSQL (db: today_events)
   │         └──► Redis (cache, Celery broker)
   ▼
Celery Worker / Beat
   │
   ▼
OpenTelemetry Collector
   ├──► Grafana Tempo (distributed traces)
   ├──► Prometheus (metrics)
   └──► Loki + Promtail (logs)
          └──► Grafana (dashboard unificata)
```

---

## Componenti principali

| Servizio | Immagine | Porta interna | Dominio dev |
|---|---|---|---|
| Traefik | traefik:v3.x | 80, 443 | traefik.127.0.0.1.nip.io |
| APISIX | apache/apisix:3.11.0 | 9080 | gateway.127.0.0.1.nip.io |
| etcd | coreos/etcd:v3.5.17 | 2379 | — |
| Keycloak | keycloak/keycloak:26.0 | 8080 | keycloak.127.0.0.1.nip.io |
| PostgreSQL | postgres:16 | 5432 | — |
| Django Backoffice | custom (python:3.11-slim) | 8000 | backoffice.127.0.0.1.nip.io |
| Frontend | custom (node:20-alpine) | 3000 | frontend.127.0.0.1.nip.io |
| Redis | redis:7 | 6379 | — |
| MinIO | minio/minio | 9000 | minio.127.0.0.1.nip.io |
| Grafana | grafana/grafana | 3000 | grafana.127.0.0.1.nip.io |
| Jaeger | jaegertracing/all-in-one | 16686 | jaeger.127.0.0.1.nip.io |

---

## Keycloak — Identity Provider

### Realm: `today-events`

Il realm centralizza tutta l'autenticazione. Non è possibile registrarsi autonomamente (`registrationAllowed: false`).

### Client registrati

| Client ID | Flow | Uso |
|---|---|---|
| `backoffice-admin` | Authorization Code (OIDC) | Browser SSO per Django Admin e API docs |
| `scraper-service` | Client Credentials (M2M) | Scrapy → Backoffice API |
| `airflow-service` | Client Credentials (M2M) | Airflow DAG → Backoffice API |

### Ruoli realm

| Ruolo | Assegnato a |
|---|---|
| `admin` | Utenti amministratori (auto-assegnato ai login Google via mapper) |
| `api-consumer` | Service accounts (scraper, airflow) |

### Scope custom

| Scope | Significato |
|---|---|
| `read` | Lettura eventi staging |
| `write` | Scrittura eventi staging |

### Identity Provider federato: Google

Keycloak federa Google OAuth2. Al login Google viene automaticamente assegnato il ruolo `admin` tramite un **identity provider mapper** (`hardcoded-role-idp-mapper`).

### Endpoint principali

```
Token:    /realms/today-events/protocol/openid-connect/token
JWKS:     /realms/today-events/protocol/openid-connect/certs
Logout:   /realms/today-events/protocol/openid-connect/logout
UserInfo: /realms/today-events/protocol/openid-connect/userinfo
Discovery: /realms/today-events/.well-known/openid-configuration
```

---

## APISIX — API Gateway

### Configurazione

APISIX legge la config da **etcd** (prefisso `/apisix`). Le route sono inizializzate da `services/apisix/init-routes.sh` all'avvio.

Plugin abilitati: `openid-connect`, `jwt-auth`, `consumer-restriction`, `limit-count`, `cors`, `prometheus`, `opentelemetry`, `proxy-rewrite`, `response-rewrite`.

### Route

| ID | Path | Auth | Upstream |
|---|---|---|---|
| 100 | `/_internal/oidc-discovery` | nessuna | Keycloak (proxy + rewrite) |
| 1 | `/admin/*` | OIDC browser SSO | Django Backoffice |
| 2 | `/static/*` | nessuna | Django Backoffice |
| 3 | `/api/public/*` | nessuna | Django Backoffice |
| 4 | `/api/external/*` | JWT Bearer (M2M) | Django Backoffice |
| 5 | `/api/*` | OIDC browser SSO | Django Backoffice |

### Route 100 — OIDC Discovery proxy

Questa route risolve un problema di rete: il plugin `openid-connect` di APISIX deve raggiungere il discovery endpoint di Keycloak, ma l'issuer pubblico nel token (`https://keycloak.domain`) non è raggiungibile dall'interno della rete Docker.

La soluzione: APISIX chiama `/_internal/oidc-discovery` che proxya `keycloak:8080/realms/today-events/.well-known/openid-configuration`, poi il plugin **response-rewrite** sostituisce gli URL degli endpoint interni (`token_endpoint`, `userinfo_endpoint`, `jwks_uri`) con indirizzi `http://keycloak:8080`, lasciando inalterati `authorization_endpoint` e `issuer` (pubblici).

---

## Flussi di autenticazione

### 1. SSO Browser — Django Admin (`/admin/*`)

Usato da: amministratori umani via browser.

```
1. Browser → GET https://gateway.domain/admin/

2. APISIX (plugin openid-connect, client: backoffice-admin)
   → Nessuna sessione → redirect:
   GET https://keycloak.domain/realms/today-events/protocol/openid-connect/auth
       ?client_id=backoffice-admin
       &redirect_uri=https://gateway.domain/admin/callback
       &response_type=code
       &scope=openid profile email

3. Keycloak mostra login page
   → Utente sceglie "Login con Google"
   → Keycloak federa a Google OAuth2
   → Google restituisce profilo a Keycloak
   → Keycloak emette authorization_code

4. Browser → GET https://gateway.domain/admin/callback?code=<code>

5. APISIX → POST keycloak:8080/realms/today-events/protocol/openid-connect/token
             (code exchange, client_secret)
           ← {access_token, id_token, refresh_token}

6. APISIX:
   - Salva sessione (cookie)
   - Estrae claim email dall'id_token
   - Aggiunge header: X-Auth-Request-Email: user@example.com
   - Proxya la richiesta a Django: GET http://backoffice:8000/admin/

7. Django — KeycloakAdminMiddleware:
   - Legge HTTP_X_AUTH_REQUEST_EMAIL
   - Cerca User.objects.get(email=email, is_active=True)
   - Verifica is_staff=True
   - Chiama login(request, user) → crea sessione Django
   - Se utente non trovato o non staff → 403 (sso_access_denied.html)

8. Browser accede all'admin con sessione Django attiva
```

**Logout:**
```
Browser → GET https://gateway.domain/admin/logout/
Django  → cancella sessione Django
        → redirect a:
          keycloak:8080/realms/today-events/protocol/openid-connect/logout
          ?post_logout_redirect_uri=https://backoffice.domain/admin/
          &client_id=backoffice-admin
Keycloak → invalida sessione SSO
         → redirect a /admin/ (richiederà nuovo login)
```

---

### 2. Client Credentials — Scraping Service (M2M)

Usato da: Scrapy spider via `ApiPipeline`.

```
1. Scrapy open_spider()
   → POST http://keycloak:8080/realms/today-events/protocol/openid-connect/token
     Content-Type: application/x-www-form-urlencoded
     Body:
       grant_type=client_credentials
       &client_id=scraper-service
       &client_secret=<secret>
       &scope=openid read write
   ← {
       "access_token": "<JWT>",
       "token_type": "Bearer",
       "expires_in": 36000,
       "scope": "openid read write"
     }

2. Scrapy processa item → buffer
   Quando buffer >= batch_size (default: 50):

3. POST https://gateway.domain/api/external/v1/staging/bulk/
   Authorization: Bearer <JWT>
   Content-Type: application/json
   Body: {"events": [...], "spider": "spider_name"}

4. APISIX Route 4 (api/external/*):
   - Plugin jwt-auth: decodifica JWT, verifica firma con JWKS
   - Plugin consumer-restriction: verifica consumer autorizzato
   - Proxya a Django: POST http://backoffice:8000/api/external/v1/staging/bulk/

5. Django — KeycloakJWTAuthentication:
   - Estrae Bearer token da Authorization header
   - Decodifica header JWT → legge kid
   - Scarica/usa cache JWKS da keycloak:8080/.../certs (TTL 5min)
   - Valida firma RS256, issuer, audience, expiry
   - Estrae: sub, realm_access.roles, scope, azp
   - Restituisce (user_or_keycloak_user, auth_info)

6. Django view verifica permessi (HasKeycloakScope / HasKeycloakRole)
   → 201 Created (sync) o 202 Accepted (async, task_id)

7. Se 401: Scrapy refresha il token e ritenta
```

---

### 3. Client Credentials — Airflow (M2M)

Stesso flusso di Scrapy con client `airflow-service`. I DAG Airflow ottengono il token Keycloak prima di chiamare le API del backoffice.

```
Configurazione Airflow:
  KEYCLOAK_TOKEN_URL: http://keycloak:8080/realms/today-events/.../token
  API_CLIENT_ID:     airflow-service
  API_CLIENT_SECRET: <secret>
```

---

## Validazione JWT in Django

`KeycloakJWTAuthentication` (DRF backend) in `backoffice/authentication.py`:

```
Authorization: Bearer <token>
       │
       ▼
Decodifica header JWT → kid
       │
       ▼
Cache JWKS (5 min TTL)  ──miss──► GET keycloak:8080/realms/today-events/.../certs
       │
       ▼
Valida con PyJWT:
  - algoritmo: RS256
  - issuer: http://keycloak:8080/realms/today-events
  - audience: account
  - expiry (exp claim)
       │
       ├─ errore ──► 401 AuthenticationFailed
       │
       ▼
Estrae payload:
  - sub          → user identifier
  - realm_access.roles → ["admin", "api-consumer", ...]
  - scope        → ["openid", "read", "write"]
  - azp          → authorized party (client_id chiamante)
       │
       ▼
Cerca User Django con username=sub
  - trovato  → restituisce User Django reale
  - non trovato → restituisce KeycloakUser fittizio (is_authenticated=True)
       │
       ▼
request.auth = {roles, scope, azp, sub}
```

### Permission classes DRF

```python
# Verifica ruolo (OR — almeno uno)
class HasKeycloakRole(BasePermission):
    required_roles = ["admin"]

# Verifica scope (AND — tutti)
class HasKeycloakScope(BasePermission):
    required_scopes = ["read", "write"]
```

---

## Struttura database PostgreSQL

Tutti i servizi condividono lo stesso container PostgreSQL ma su database separati:

| Database | Owner | Usato da |
|---|---|---|
| `today_events` | events | Django Backoffice, Airflow (metadata) |
| `keycloak` | events | Keycloak (sessioni, realm, client) |
| `n8n` | events | n8n workflow automation |
| `sonarqube` | events | SonarQube code quality |
| `backstage` | events | Backstage developer portal |

---

## Observability

Ogni componente invia span OpenTelemetry al collector (`otel-collector:4317`):

| Sorgente | Span emessi |
|---|---|
| Keycloak (`KC_TRACING_ENABLED=true`) | token_issued, login, logout |
| APISIX (plugin opentelemetry) | route match, upstream latency, consumer |
| Django (opentelemetry-instrumentation-django) | view, ORM query, middleware |
| Celery (opentelemetry-instrumentation-celery) | task execution, retry |

**Pipeline traces:** OTel Collector → **Grafana Tempo** (storage) → **Grafana** (UI)

**Pipeline metrics:** APISIX Prometheus endpoint + Django django-prometheus → **Prometheus** → **Grafana**

**Pipeline logs:** Promtail raccoglie log Docker → **Loki** → **Grafana**

---

## Avvio stack di sviluppo

```bash
cd infrastructures
make up
```

Al primo avvio su volume Postgres vuoto, lo script `services/postgres/init.d/02-databases.sql` crea automaticamente i database `keycloak`, `n8n`, `sonarqube`, `backstage`.

Se il volume esiste già (upgrade), crearli manualmente:
```bash
docker compose exec -T postgres psql -U events -d today_events -c "
  CREATE DATABASE keycloak OWNER events;
  CREATE DATABASE backstage OWNER events;
"
```

Django esegue `migrate` automaticamente all'avvio tramite `entrypoint.sh`.

Servizi disponibili:

| URL | Servizio | Credenziali dev |
|---|---|---|
| https://frontend.127.0.0.1.nip.io | Frontend React | — |
| https://backoffice.127.0.0.1.nip.io/admin/ | Django Admin (via SSO) | admin / admin (Keycloak) |
| https://gateway.127.0.0.1.nip.io | API Gateway APISIX | — |
| https://keycloak.127.0.0.1.nip.io | Keycloak Admin | admin / admin_secret_2026 |
| https://apisix-dashboard.127.0.0.1.nip.io | APISIX Dashboard | admin / admin |
| https://grafana.127.0.0.1.nip.io | Grafana | admin / admin |
| https://jaeger.127.0.0.1.nip.io | Jaeger Traces | — |
| https://minio.127.0.0.1.nip.io | MinIO Console | minioadmin / minioadmin_secret_2026 |
| https://traefik.127.0.0.1.nip.io | Traefik Dashboard | — |
