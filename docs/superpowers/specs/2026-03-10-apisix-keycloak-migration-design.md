# Migrazione Kong → APISIX + Keycloak

**Data:** 2026-03-10
**Stato:** Approvato

## Motivazione

- Centralizzare autenticazione in un unico IdP (Keycloak)
- Funzionalità APISIX (dashboard, plugin ecosystem, etcd-based)
- Costi/licensing Kong Enterprise

## Architettura

```
Internet → Traefik (TLS/edge) → APISIX (API Gateway) → Django Backoffice
                                      ↕                       ↕
                                  Keycloak (IdP)          Celery Worker
                                      ↓                       ↓
                               OpenTelemetry Collector ←───────┘
                                 ↓              ↓
                              Tempo         Prometheus
                                 └──── Grafana ────┘
```

**Componenti:**
- **Traefik** — TLS termination, IngressRoute, edge routing
- **APISIX + etcd + Dashboard** — API gateway con plugin OIDC, rate-limiting, CORS
- **Keycloak + PostgreSQL** — SSO, client credentials, Google IdP federato
- **Django Backoffice** — valida JWT da Keycloak (rimuove django-oauth-toolkit)

## 1. Keycloak: Realm e Client

```
Realm: today-events
├── Client: backoffice-admin    (authorization code, browser SSO)
│   ├── Redirect URI: https://gateway.{domain}/*
│   ├── Web Origins: https://gateway.{domain}
│   └── Roles: admin
├── Client: scraper-service     (client credentials)
│   └── Roles: api-consumer
├── Client: airflow-service     (client credentials)
│   └── Roles: api-consumer
├── Identity Provider: google   (Google OpenID Connect federato)
│   └── Mapper: email → username, ruolo admin auto-assegnato
├── Realm Roles: admin, api-consumer
├── Scopes: read, write
└── Events Config:
    ├── Login events: enabled
    ├── Admin events: enabled
    └── Event listeners: [jboss-logging, metrics-listener]
```

**Realm template:** `infrastructures/services/keycloak/realm-today-events.json`
- Importato automaticamente al primo avvio di Keycloak
- Realm settings (token lifetime, refresh policy, brute force protection)
- Client definitions con secret placeholder
- Google Identity Provider pre-configurato
- Role mapping automatico
- Event logging per monitoring
- SMTP config placeholder per email

## 2. APISIX: Route e Plugin

| Route | Path | Auth | Plugin |
|-------|------|------|--------|
| api-external | `/api/external/*` | JWT (client credentials) | jwt-auth, consumer-restriction, limit-count, cors, opentelemetry |
| api-public | `/api/public/*` | nessuna | cors, opentelemetry |
| gateway-admin | `/admin/*` | OIDC (browser SSO) | openid-connect, consumer-restriction, opentelemetry |
| gateway-api | `/api/*` | OIDC (browser SSO) | openid-connect, consumer-restriction, opentelemetry |
| gateway-static | `/static/*` | nessuna | — |

**Plugin globali:** opentelemetry, prometheus

**Consumer APISIX:**
- `scraper` — validazione JWT, gruppo `api-consumer`
- `airflow` — validazione JWT, gruppo `api-consumer`
- `admin-sso` — sessione OIDC, gruppo `admin`

## 3. Dev: docker-compose

**Nuovi servizi:**
```yaml
apisix:            # apache/apisix:3.11
etcd:              # bitnami/etcd:3.5
apisix-dashboard:  # apache/apisix-dashboard:3.0
keycloak:          # quay.io/keycloak/keycloak:26
tempo:             # grafana/tempo:2.6
```

**Servizi rimossi:** `kong`, `kong-migrations`, `oauth2-proxy`

**DB rimossi:** `kong`. **DB aggiunti:** `keycloak`

**Traefik labels:**
- `keycloak.{DOMAIN}` → Keycloak (porta 8080)
- `apisix-dashboard.{DOMAIN}` → Dashboard (porta 9000)
- `gateway.{DOMAIN}` → APISIX proxy (porta 9080)

## 4. Produzione: OKE/K8s

**Nuova directory:** `infrastructures/OCI/k8s/apisix/`
- Helm chart APISIX + Ingress Controller
- CRD: `ApisixRoute`, `ApisixUpstream`, `ApisixPluginConfig`
- `kustomization.yml`

**Nuova directory:** `infrastructures/OCI/k8s/keycloak/`
- Helm chart Bitnami Keycloak
- ConfigMap con realm template
- Secret per DB password e admin credentials
- IngressRoute per `auth.{domain}`

**Nuovo playbook:** `infrastructures/OCI/ansible/playbooks/apisix-keycloak-setup.yml`
- Crea DB `keycloak` in PostgreSQL
- Deploy Keycloak via Helm con realm template
- Deploy APISIX + etcd via Helm
- Configura Google IdP con credenziali vault
- Applica CRD per route

**Rimosso:** `k8s/kong/`, `kong-setup.yml`, `k8s/oauth/`

## 5. Modifiche Django

- **Rimuovi:** `django-oauth-toolkit`, URL `/oauth/`, modelli OAuth2
- **Aggiungi:** `PyJWT` + `cryptography` per validazione JWT via JWKS
- **Nuovo auth backend DRF:** `KeycloakJWTAuthentication`
  - Scarica JWKS da `keycloak/realms/today-events/protocol/openid-connect/certs`
  - Valida firma, expiry, audience, issuer
  - Estrae ruoli dal claim `realm_access.roles`
- **Settings:** `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_AUDIENCE`
- `SessionAuthentication` resta per admin (sessione gestita da APISIX OIDC plugin)

## 6. Modifiche Scraper/Airflow

- **Scraper pipeline:** sostituisci OAuth2 token request (Django) con Keycloak token endpoint
- **Airflow DAG:** aggiorna token acquisition per Keycloak endpoint
- Stesso flusso: `client_id` + `client_secret` → JWT → `Authorization: Bearer`

## 7. Observability: Trace End-to-End

**Catena OpenTelemetry:**
```
Keycloak (KC_TRACING_ENABLED=true)
    → span: token_issued, login, refresh
APISIX (plugin opentelemetry)
    → span: route, upstream, consumer, status
Django (opentelemetry-instrumentation-django)
    → span: view, db query
Celery (opentelemetry-instrumentation-celery)
    → span: task execution
         ↓ tutti convergono in
OpenTelemetry Collector → Tempo (traces) + Prometheus (metriche)
         ↓
      Grafana
```

**Grafana Dashboard preconfigurate:**
1. **API Gateway** — request/sec, latenza p95, errori per route/consumer
2. **Keycloak** — login success/failure, token attivi, sessioni per client
3. **Distributed Tracing** — trace waterfall, tempo per servizio, error rate
4. **Rate Limiting** — hit rate per consumer, rejected requests

## 8. Flussi di Autenticazione

### Scraper/Airflow (M2M)
```
Scraper → POST keycloak/realms/today-events/protocol/openid-connect/token
          (client_id + client_secret, grant_type=client_credentials)
       ← JWT access_token
Scraper → GET apisix/api/external/v1/staging/
          Authorization: Bearer <JWT>
APISIX  → valida JWT (JWKS), verifica consumer → proxy a Django
```

### Admin browser (SSO)
```
Browser → GET gateway.domain/admin/
APISIX  → redirect a Keycloak login (Google IdP federato)
       ← authorization code → token exchange
APISIX  → set session cookie, proxy a Django
```

### Utenti esterni API
```
Nuovo client Keycloak → client_id + client_secret
                      → stesso flusso M2M di scraper/airflow
```

## 9. File e Directory

```
infrastructures/
├── services/
│   ├── apisix/
│   │   ├── config.yaml              # APISIX config (dev)
│   │   └── dashboard.yaml           # Dashboard config (dev)
│   ├── keycloak/
│   │   └── realm-today-events.json  # Realm template
│   └── grafana/
│       └── dashboards/
│           ├── apisix.json
│           ├── keycloak.json
│           └── tracing.json
├── OCI/k8s/
│   ├── apisix/                      # NUOVO (sostituisce kong/)
│   │   ├── apisix-values.yml
│   │   ├── apisix-routes.yml        # CRD
│   │   └── kustomization.yml
│   └── keycloak/                    # NUOVO (sostituisce oauth/)
│       ├── keycloak-values.yml
│       ├── keycloak-realm-configmap.yml
│       └── kustomization.yml
└── docker-compose.dev.yml           # Aggiornato
```
