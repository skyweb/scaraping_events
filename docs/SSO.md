# SSO — Single Sign-On (APISIX + Keycloak)

Tutti i servizi web dello stack sono esposti tramite **APISIX** (API Gateway) che gestisce TLS termination e autenticazione OIDC con **Keycloak** come Identity Provider.

## Architettura

```
Browser
   │
   │  HTTPS (*.127.0.0.1.nip.io)
   ▼
┌──────────────────────────────────────────────────────┐
│  APISIX (TLS termination + plugin openid-connect)    │
│                                                      │
│  1. Verifica sessione OIDC                           │
│  2. Se assente → redirect a Keycloak login           │
│  3. Keycloak autentica → redirect callback           │
│  4. APISIX salva sessione, inietta header:           │
│     • X-Userinfo (JSON base64 con claim OIDC)        │
│     • X-Id-Token (JWT ID token)                      │
│     • X-Access-Token (JWT access token)              │
│  5. Proxy verso upstream                             │
└──────────────────────────────────────────────────────┘
   │
   │  Header iniettati
   ▼
┌──────────────┐
│  Upstream     │  (Django, Grafana, Airflow, ...)
│  Service      │  legge gli header per identificare l'utente
└──────────────┘
```

## Keycloak — Realm e Ruoli

**Realm**: `today-events`

### Ruoli realm

| Ruolo | Descrizione | Servizi abilitati |
|---|---|---|
| `admin` | Amministratore completo | Django Admin (superuser), Airflow (Admin), Grafana, tutti |
| `web` | Redazione contenuti | Django Admin (gruppo Redazione, permessi limitati) |
| `monitoring` | Operatore monitoring | Airflow (Viewer, sola lettura), Grafana, Prometheus, Flower |
| `api-consumer` | Consumatore API esterne | Solo API `/api/v1/events/` via JWT bearer |

### Utenti creati al primo avvio

| Utente | Password | Ruoli | Tipo |
|---|---|---|---|
| `admin` | `admin_secret_2026` | `admin`, `web`, `monitoring` | Utente interattivo |
| `service-account-backoffice-admin` | — | `manage-clients`, `create-client` | Service account (client credentials) |

### Client OIDC

| Client ID | Tipo | Utilizzato da |
|---|---|---|
| `backoffice-admin` | Confidential | APISIX (SSO per tutti i servizi web) |
| `scraper-service` | Confidential | Scraping service (client credentials → API) |
| `minio-console` | Confidential | MinIO (OIDC login console) |
| `harbor` | Confidential | Harbor Registry (OIDC login UI) |
| `airflow-service` | Confidential | Airflow (non usato direttamente, SSO via APISIX) |

---

## Flussi SSO per servizio

### 1. Django Admin

| | |
|---|---|
| **URL** | `https://backoffice.${DOMAIN}/admin/` |
| **Route APISIX** | ID 200, `oidc_route` su `/admin/*` |
| **Meccanismo** | Middleware `KeycloakAdminMiddleware` legge `X-Userinfo` |
| **Ruoli richiesti** | `admin` oppure `web` |
| **Senza ruolo** | Pagina 403 `sso_access_denied.html` |

**Flusso dettagliato:**

```
Browser → APISIX (openid-connect) → Keycloak login
   → callback → APISIX salva sessione, inietta X-Userinfo
   → Django KeycloakAdminMiddleware:
      1. Decodifica X-Userinfo (JSON)
      2. Estrae email e realm_access.roles
      3. Verifica ruolo "admin" o "web"
      4. Se utente Django non esiste → auto-provisioning:
         • admin → is_superuser=True, is_staff=True
         • web   → is_staff=True, gruppo "Redazione" (permessi limitati)
      5. login() automatico
```

**Mapping ruoli:**

| Ruolo Keycloak | Utente Django | Permessi |
|---|---|---|
| `admin` | `is_superuser=True` | Accesso completo a tutti i modelli |
| `web` | Gruppo `Redazione` | Solo `view_event` (configurabile in `REDAZIONE_PERMISSIONS`) |
| nessuno | **Accesso negato** (403) | — |

**Logout:** `https://backoffice.${DOMAIN}/admin/logout/` → cancella sessione Django → redirect a `/admin/sso-logout` (intercettato da APISIX che fa logout OIDC su Keycloak).

---

### 2. Grafana

| | |
|---|---|
| **URL** | `https://grafana.${DOMAIN}/` |
| **Route APISIX** | ID 201, `oidc_route_grafana` su `/*` |
| **Meccanismo** | Auth Proxy (`X-Auth-Request-Email`) |
| **Ruoli richiesti** | Nessuno (chiunque autenticato su Keycloak) |
| **Ruolo Grafana** | Tutti `Admin` (configurato in `GF_USERS_AUTO_ASSIGN_ORG_ROLE`) |

**Flusso dettagliato:**

```
Browser → APISIX (openid-connect) → Keycloak login
   → callback → APISIX:
      1. Decodifica X-Userinfo (base64 JSON)
      2. Lua serverless-post-function estrae email
      3. Imposta header X-Auth-Request-Email
   → Grafana (auth proxy):
      1. Legge X-Auth-Request-Email
      2. Se utente non esiste → auto sign-up
      3. Assegna ruolo Admin
```

**Configurazione Grafana rilevante:**

```
GF_AUTH_PROXY_ENABLED=true
GF_AUTH_PROXY_HEADER_NAME=X-Auth-Request-Email
GF_AUTH_DISABLE_LOGIN_FORM=true
GF_USERS_AUTO_ASSIGN_ORG_ROLE=Admin
```

> Il login form nativo di Grafana è disabilitato — l'unico accesso è via SSO.

---

### 3. Airflow

| | |
|---|---|
| **URL** | `https://airflow.${DOMAIN}/` |
| **Route APISIX** | ID 207, route custom con estrazione email + ruoli |
| **Route statica** | ID 305, `/static/*` senza auth (priority 10) |
| **Meccanismo** | Auth Proxy (`X-Auth-Request-Email` + `X-Auth-Request-Roles`) |
| **Ruoli richiesti** | `admin` oppure `monitoring` |
| **Senza ruolo** | Registrazione bloccata / utente disattivato |

**Flusso dettagliato:**

```
Browser → APISIX (openid-connect) → Keycloak login
   → callback → APISIX:
      1. Decodifica X-Userinfo (base64 JSON)
      2. Lua serverless-post-function:
         a. Estrae email → X-Auth-Request-Email
         b. Estrae realm_access.roles → X-Auth-Request-Roles (comma-separated)
   → Airflow (AUTH_REMOTE_USER):
      1. Legge email da HTTP_X_AUTH_REQUEST_EMAIL
      2. KeycloakRoleSecurityManager:
         a. Legge X-Auth-Request-Roles
         b. Mappa admin → Admin, monitoring → Viewer
         c. Se nessun ruolo valido → blocca registrazione / disattiva utente
```

**Mapping ruoli:**

| Ruolo Keycloak | Ruolo Airflow | Permessi |
|---|---|---|
| `admin` | **Admin** | Accesso completo (DAG, config, connessioni, trigger) |
| `monitoring` | **Viewer** | Sola lettura (vede DAG, log, stato — non può modificare) |
| nessuno | **Bloccato** | `auth_user_registration()` → `False`, utente disattivato |

**Aggiornamento dinamico:** il ruolo viene sincronizzato ad ogni accesso tramite `load_user()`. Se un utente perde il ruolo in Keycloak, viene disattivato su Airflow. Se lo riacquista, viene riattivato.

**File di configurazione:** `services/airflow/webserver_config.py`

---

### 4. Prometheus

| | |
|---|---|
| **URL** | `https://prometheus.${DOMAIN}/` |
| **Route APISIX** | ID 202, `oidc_route` su `/*` |
| **Meccanismo** | Solo gate APISIX (Prometheus non ha auth interna) |
| **Ruoli richiesti** | Nessuno (chiunque autenticato su Keycloak) |

**Flusso:**

```
Browser → APISIX (openid-connect) → Keycloak login → proxy a Prometheus
```

Prometheus non gestisce utenti — APISIX funge da gate. Se autenticato su Keycloak, si accede.

---

### 5. Flower (Celery monitoring)

| | |
|---|---|
| **URL** | `https://flower.${DOMAIN}/` |
| **Route APISIX** | ID 203, `oidc_route` su `/*` |
| **Meccanismo** | Solo gate APISIX (Flower non ha auth interna) |
| **Ruoli richiesti** | Nessuno (chiunque autenticato su Keycloak) |

**Flusso:** identico a Prometheus.

---

### 6. APISIX Dashboard

| | |
|---|---|
| **URL** | `https://apisix-dashboard.${DOMAIN}/` |
| **Route APISIX** | ID 208, `oidc_route` su `/*` |
| **Meccanismo** | Solo gate APISIX |
| **Ruoli richiesti** | Nessuno (chiunque autenticato su Keycloak) |

**Flusso:** identico a Prometheus.

---

### 7. Redis Exporter / Celery Exporter

| | |
|---|---|
| **URL** | `https://redis-exporter.${DOMAIN}/`, `https://celery-exporter.${DOMAIN}/` |
| **Route APISIX** | ID 205, 206, `oidc_route` su `/*` |
| **Meccanismo** | Solo gate APISIX |
| **Ruoli richiesti** | Nessuno (chiunque autenticato su Keycloak) |

---

### 8. Scrapyd

| | |
|---|---|
| **URL** | `https://scrapyd.${DOMAIN}/` |
| **Route APISIX** | ID 209, `oidc_route` su `/*` |
| **Meccanismo** | Solo gate APISIX |
| **Ruoli richiesti** | Nessuno (chiunque autenticato su Keycloak) |

---

### 9. Loki

| | |
|---|---|
| **URL** | `https://loki.${DOMAIN}/` |
| **Route APISIX** | ID 210, `oidc_route` su `/*` |
| **Meccanismo** | Solo gate APISIX |
| **Ruoli richiesti** | Nessuno (chiunque autenticato su Keycloak) |

---

## Servizi SENZA SSO

| Servizio | URL | Autenticazione | Note |
|---|---|---|---|
| **Harbor Registry** | `https://registry.${DOMAIN}/` | Auth interna Harbor (OIDC configurabile) | Route APISIX senza plugin openid-connect |
| **MinIO** | `https://minio.${DOMAIN}/` | Login locale (`minioadmin` / da `.env`) | OIDC configurato ma via Keycloak diretto, non APISIX |
| **Mailpit** | `https://mail.${DOMAIN}/` | Nessuna (solo dev) | Route APISIX senza auth |
| **API esterne** | `https://webservice.${DOMAIN}/api/v1/events/` | JWT Bearer (OAuth2 client credentials) | Token ottenuto via `POST /realms/today-events/protocol/openid-connect/token` |

---

## Riepilogo matrice accesso

| Servizio | `admin` | `web` | `monitoring` | nessun ruolo |
|---|---|---|---|---|
| Django Admin | Superuser | Redazione (view only) | **Negato** | **Negato** |
| Airflow | Admin | **Negato** | Viewer | **Negato** |
| Grafana | Admin | Admin | Admin | Admin |
| Prometheus | Accesso | Accesso | Accesso | Accesso |
| Flower | Accesso | Accesso | Accesso | Accesso |
| APISIX Dashboard | Accesso | Accesso | Accesso | Accesso |
| Scrapyd | Accesso | Accesso | Accesso | Accesso |

> **Nota**: Prometheus, Flower, APISIX Dashboard, Scrapyd, Loki, Redis/Celery Exporter non hanno gestione ruoli interna — chiunque sia autenticato su Keycloak (qualsiasi ruolo realm) può accedervi. Il gate è l'autenticazione OIDC stessa.

---

## File di configurazione

| File | Descrizione |
|---|---|
| `services/keycloak/realm-today-events.json` | Realm import (utenti, ruoli, client, scopes) |
| `services/apisix/init-routes.sh` | Route APISIX con plugin openid-connect |
| `services/apisix/config.yaml` | Config APISIX (TLS, SNI) |
| `services/airflow/webserver_config.py` | Custom security manager con mapping ruoli |
| `services/grafana/` → docker-compose env | Auth proxy config (`GF_AUTH_PROXY_*`) |
| `backoffice/middleware.py` | `KeycloakAdminMiddleware` (SSO Django Admin) |

---

## Creare nuovi utenti

```bash
# Via Makefile (crea utente Keycloak con email di attivazione)
make create-user EMAIL=mario@example.com FIRST=Mario LAST=Rossi ROLES="web monitoring"
```

Ruoli disponibili: `admin`, `web`, `monitoring`, `api-consumer`
