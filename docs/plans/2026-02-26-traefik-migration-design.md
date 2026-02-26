# Traefik Migration Design

**Date:** 2026-02-26
**Scope:** Dev environment only (`infrastructures/docker-compose.dev.yml`)
**Goal:** Replace nginx reverse proxy with Traefik; each service accessible at `servicename.domain.tld` where `domain.tld` comes from `.env`.

---

## Architecture

### DNS Strategy

Use `nip.io` for zero-config local DNS resolution.

```
DOMAIN=127.0.0.1.nip.io
```

`grafana.127.0.0.1.nip.io` resolves automatically to `127.0.0.1` — no `/etc/hosts` edits needed.

### Traefik Setup

- Image: `traefik:v3.1`
- Docker provider reads labels from containers on `dev-network`
- `exposedByDefault: false` — only containers with `traefik.enable=true` are routed
- Entrypoint `web` on port `80`
- Dashboard exposed on `traefik.${DOMAIN}` (protected by ForwardAuth)
- No separate config files — all routing defined as Docker labels

### Subdomain Map

| Subdomain | Service | Internal Port | Auth |
|---|---|---|---|
| `frontend.${DOMAIN}` | frontend | 5173 | No |
| `backoffice.${DOMAIN}` | backoffice | 8000 | `/admin/` only |
| `grafana.${DOMAIN}` | grafana | 3001 | Yes |
| `jaeger.${DOMAIN}` | jaeger | 16686 | Yes |
| `prometheus.${DOMAIN}` | prometheus | 9090 | Yes |
| `superset.${DOMAIN}` | superset | 8088 | Yes |
| `airflow.${DOMAIN}` | airflow-webserver | 8080 | Yes |
| `flower.${DOMAIN}` | flower | 5555 | Yes |
| `loki.${DOMAIN}` | loki | 3100 | Yes |
| `n8n.${DOMAIN}` | n8n | 5678 | Yes |
| `ollama.${DOMAIN}` | ollama | 11434 | Yes |
| `cadvisor.${DOMAIN}` | cadvisor | 8080 | Yes |
| `redis-exporter.${DOMAIN}` | redis-exporter | 9121 | Yes |
| `scrapyd.${DOMAIN}` | scrapyd | 6800 | Yes |
| `auth.${DOMAIN}` | oauth2-proxy | 4180 | No (public) |
| `traefik.${DOMAIN}` | traefik dashboard | api@internal | Yes |

---

## Auth Flow

### ForwardAuth Middleware

Defined as labels on the `oauth2-proxy` service:

```
traefik.http.middlewares.forward-auth.forwardauth.address=http://oauth2-proxy:4180/oauth2/auth
traefik.http.middlewares.forward-auth.forwardauth.trustForwardHeader=true
traefik.http.middlewares.forward-auth.forwardauth.authResponseHeaders=X-Auth-Request-User,X-Auth-Request-Email,Set-Cookie
```

Protected services add: `traefik.http.routers.<name>.middlewares=forward-auth`

### Auth Flow Steps

1. Request arrives at `grafana.${DOMAIN}`
2. Traefik calls `oauth2-proxy:4180/oauth2/auth`
3. Not authenticated → oauth2-proxy returns 302 → browser redirected to `auth.${DOMAIN}/oauth2/sign_in?rd=<original_url>`
4. Google login completes → callback at `auth.${DOMAIN}/oauth2/callback`
5. Cookie set with domain `.${DOMAIN}` → works for all subdomains
6. Redirect back to original URL

### oauth2-proxy Config Changes

| Variable | Old | New |
|---|---|---|
| `OAUTH2_PROXY_REDIRECT_URL` | `http://localhost/oauth2/callback` | `http://auth.${DOMAIN}/oauth2/callback` |
| `OAUTH2_PROXY_COOKIE_DOMAIN` | _(not set)_ | `.${DOMAIN}` |

> **Note:** The Google OAuth app must add `http://auth.${DOMAIN}/oauth2/callback` as an authorized redirect URI.

### Backoffice Special Case

Two Traefik routers on the same service with different priorities:

- `backoffice-admin` router: `Host('backoffice.${DOMAIN}') && PathPrefix('/admin/')` + `forward-auth` middleware, priority 10
- `backoffice` router: `Host('backoffice.${DOMAIN}')`, priority 1

Both route to the same backoffice container on port 8000.

---

## Service Config Changes

Services were previously configured to serve under a sub-path via nginx. With each service on its own subdomain they serve from root `/`.

### Grafana
- Remove `GF_SERVER_SERVE_FROM_SUB_PATH: "true"`
- Change `GF_SERVER_ROOT_URL` to `http://grafana.${DOMAIN}/`

### Prometheus
- Remove `--web.route-prefix=/prometheus`
- Remove `--web.external-url=http://localhost/prometheus`

### Airflow
- Change `AIRFLOW__WEBSERVER__BASE_URL` to `http://airflow.${DOMAIN}`
- Applied to: `airflow-init`, `airflow-webserver`, `airflow-scheduler`

### n8n
- Remove `N8N_PATH: /n8n/`
- Change `WEBHOOK_URL` to `http://n8n.${DOMAIN}/`
- Change `N8N_EDITOR_BASE_URL` to `http://n8n.${DOMAIN}/`

### Flower
- Remove `--url-prefix=flower` from command

### cAdvisor
- Remove `--url_base_prefix=/cadvisor` from command

### Superset (`superset_config.py`)
- Remove `x_prefix` from `PROXY_FIX_CONFIG` (no sub-path stripping needed)
- Keep `ENABLE_PROXY_FIX = True` and `x_for/x_proto/x_host` for correct IP forwarding

### Backoffice
- `DJANGO_ALLOWED_HOSTS` updated to include `backoffice.${DOMAIN}`
- `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` updated to include `http://frontend.${DOMAIN}`

### Frontend
- `VITE_API_URL` changed from `http://localhost/api` to `http://backoffice.${DOMAIN}/api`

---

## Files Changed

| File | Change |
|---|---|
| `infrastructures/docker-compose.dev.yml` | Remove nginx; add traefik service; add Traefik labels to all services; update env vars |
| `infrastructures/.env.example` | Add `DOMAIN=127.0.0.1.nip.io` |
| `infrastructures/services/superset/superset_config.py` | Remove `x_prefix` from `PROXY_FIX_CONFIG` |
| `microservices/scraping-service/docker-compose.yml` | Add Traefik labels for `scrapyd.${DOMAIN}` with `forward-auth` |
| `infrastructures/services/nginx/nginx.conf` | Deleted |
| `infrastructures/services/nginx/502.html` | Deleted (if exists) |

`scraping-comuni-service` is a one-shot job with no HTTP interface — no Traefik labels needed.
