# Traefik Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace nginx with Traefik in the dev stack so each service is accessible at `servicename.${DOMAIN}` where `DOMAIN` comes from `.env`.

**Architecture:** Traefik reads Docker labels to discover routes; all routing config lives as labels on each container. oauth2-proxy becomes a Traefik `ForwardAuth` middleware that protects services requiring Google SSO. Services previously configured for sub-path serving (Grafana, Prometheus, Airflow, n8n, Flower, cAdvisor, Jaeger) are reconfigured to serve from root `/`.

**Tech Stack:** Traefik v3.1, Docker Compose labels, oauth2-proxy ForwardAuth, nip.io DNS

**Design doc:** `docs/plans/2026-02-26-traefik-migration-design.md`

---

## Task 1: Add DOMAIN to env files

**Files:**
- Modify: `infrastructures/.env.example`
- Modify: `microservices/scraping-service/.env.example`

**Step 1: Add DOMAIN to infrastructure .env.example**

At the bottom of `infrastructures/.env.example`, add:

```
# Traefik — dominio base per tutti i sottodomini
# Usare nip.io per resoluzione automatica in locale: 127.0.0.1.nip.io
# Oppure impostare un dominio reale in produzione.
DOMAIN=127.0.0.1.nip.io
```

**Step 2: Add DOMAIN to scraping-service .env.example**

At the bottom of `microservices/scraping-service/.env.example`, add:

```
# Traefik — dominio base (deve coincidere con infrastructures/.env)
DOMAIN=127.0.0.1.nip.io
```

**Step 3: Commit**

```bash
git add infrastructures/.env.example microservices/scraping-service/.env.example
git commit -m "feat(infra): add DOMAIN variable for Traefik subdomain routing"
```

---

## Task 2: Add Traefik service to docker-compose.dev.yml

**Files:**
- Modify: `infrastructures/docker-compose.dev.yml`

**Step 1: Add the Traefik service block**

Add this service block **before** the `# Redis Exporter` comment (after the `nginx` block — nginx will be removed in Task 12):

```yaml
  # Traefik — reverse proxy e service discovery via Docker labels
  traefik:
    image: traefik:v3.1
    container_name: dev-traefik
    restart: unless-stopped
    command:
      - --providers.docker=true
      - --providers.docker.exposedbydefault=false
      - --providers.docker.network=dev-network
      - --entrypoints.web.address=:80
      - --api.dashboard=true
      - --api.insecure=true
      - --log.level=INFO
    ports:
      - "80:80"
      - "8082:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.traefik-dashboard.rule=Host(`traefik.${DOMAIN}`)"
      - "traefik.http.routers.traefik-dashboard.entrypoints=web"
      - "traefik.http.routers.traefik-dashboard.service=api@internal"
      - "traefik.http.routers.traefik-dashboard.middlewares=forward-auth"
    networks:
      - dev-network
```

**Step 2: Verify syntax**

```bash
cd infrastructures && docker compose -f docker-compose.dev.yml config --quiet
```
Expected: no output (no errors).

**Step 3: Commit**

```bash
git add infrastructures/docker-compose.dev.yml
git commit -m "feat(infra): add Traefik service with Docker provider"
```

---

## Task 3: Update oauth2-proxy (ForwardAuth middleware + new redirect URL)

**Files:**
- Modify: `infrastructures/docker-compose.dev.yml`

**Step 1: Add labels and update env on the oauth2-proxy service**

Find the `oauth2-proxy:` service block. Make these changes:

1. Change `OAUTH2_PROXY_REDIRECT_URL`:
   ```yaml
   OAUTH2_PROXY_REDIRECT_URL: "http://auth.${DOMAIN}/oauth2/callback"
   ```

2. Add after `OAUTH2_PROXY_REAL_CLIENT_IP_HEADER`:
   ```yaml
   # Cookie cross-subdomain: tutti i servizi sotto .${DOMAIN} condividono la sessione
   OAUTH2_PROXY_COOKIE_DOMAIN: ".${DOMAIN}"
   ```

3. Add `labels:` block before `depends_on:`:
   ```yaml
   labels:
     - "traefik.enable=true"
     # Route pubblica per sign_in, callback, sign_out, userinfo
     - "traefik.http.routers.auth.rule=Host(`auth.${DOMAIN}`)"
     - "traefik.http.routers.auth.entrypoints=web"
     - "traefik.http.services.auth.loadbalancer.server.port=4180"
     # Middleware ForwardAuth — usato da tutti i servizi protetti
     - "traefik.http.middlewares.forward-auth.forwardauth.address=http://oauth2-proxy:4180/oauth2/auth"
     - "traefik.http.middlewares.forward-auth.forwardauth.trustForwardHeader=true"
     - "traefik.http.middlewares.forward-auth.forwardauth.authResponseHeaders=X-Auth-Request-User,X-Auth-Request-Email,Set-Cookie"
   ```

> **Note:** After updating `.env`, the Google OAuth app in Google Console must add `http://auth.${DOMAIN}/oauth2/callback` as an authorized redirect URI.

**Step 2: Verify syntax**

```bash
cd infrastructures && docker compose -f docker-compose.dev.yml config --quiet
```

**Step 3: Commit**

```bash
git add infrastructures/docker-compose.dev.yml
git commit -m "feat(infra): configure oauth2-proxy as Traefik ForwardAuth middleware"
```

---

## Task 4: Update frontend service

**Files:**
- Modify: `infrastructures/docker-compose.dev.yml`

**Step 1: Add labels and update VITE_API_URL**

Find the `frontend:` service block:

1. Change `VITE_API_URL`:
   ```yaml
   VITE_API_URL: http://backoffice.${DOMAIN}/api
   ```

2. Remove the `ports:` block (Traefik handles routing — no need to expose port on host):
   ```yaml
   # Remove these lines:
   ports:
     - "${FRONTEND_PORT:-3000}:5173"
   ```

3. Add `labels:` block before `networks:`:
   ```yaml
   labels:
     - "traefik.enable=true"
     - "traefik.http.routers.frontend.rule=Host(`frontend.${DOMAIN}`)"
     - "traefik.http.routers.frontend.entrypoints=web"
     - "traefik.http.services.frontend.loadbalancer.server.port=5173"
   ```

**Step 2: Verify**

```bash
cd infrastructures && docker compose -f docker-compose.dev.yml config --quiet
```

**Step 3: Commit**

```bash
git add infrastructures/docker-compose.dev.yml
git commit -m "feat(infra): route frontend via Traefik at frontend.\${DOMAIN}"
```

---

## Task 5: Update backoffice service (dual router for /admin/ protection)

**Files:**
- Modify: `infrastructures/docker-compose.dev.yml`

**Step 1: Update environment variables**

Find the `backoffice:` service block and update:

```yaml
DJANGO_ALLOWED_HOSTS: "backoffice.${DOMAIN},backoffice,localhost,127.0.0.1"
CORS_ALLOWED_ORIGINS: "http://frontend.${DOMAIN},http://localhost:3000"
CSRF_TRUSTED_ORIGINS: "http://frontend.${DOMAIN},http://localhost:3000"
```

**Step 2: Remove exposed port**

Remove:
```yaml
ports:
  - "${BACKOFFICE_PORT:-8000}:8000"
```

**Step 3: Add labels with dual-router for /admin/ protection**

Add `labels:` block before `depends_on:`:
```yaml
labels:
  - "traefik.enable=true"
  # Router protetto per /admin/ — priorità alta
  - "traefik.http.routers.backoffice-admin.rule=Host(`backoffice.${DOMAIN}`) && PathPrefix(`/admin/`)"
  - "traefik.http.routers.backoffice-admin.entrypoints=web"
  - "traefik.http.routers.backoffice-admin.service=backoffice-svc"
  - "traefik.http.routers.backoffice-admin.middlewares=forward-auth"
  - "traefik.http.routers.backoffice-admin.priority=10"
  # Router default per API, static, oauth2 — nessuna auth
  - "traefik.http.routers.backoffice.rule=Host(`backoffice.${DOMAIN}`)"
  - "traefik.http.routers.backoffice.entrypoints=web"
  - "traefik.http.routers.backoffice.service=backoffice-svc"
  - "traefik.http.routers.backoffice.priority=1"
  # Definizione servizio (condivisa tra i due router)
  - "traefik.http.services.backoffice-svc.loadbalancer.server.port=8000"
```

**Step 4: Verify**

```bash
cd infrastructures && docker compose -f docker-compose.dev.yml config --quiet
```

**Step 5: Commit**

```bash
git add infrastructures/docker-compose.dev.yml
git commit -m "feat(infra): route backoffice via Traefik, protect /admin/ with ForwardAuth"
```

---

## Task 6: Update Grafana, Prometheus, Jaeger

**Files:**
- Modify: `infrastructures/docker-compose.dev.yml`
- Modify: `infrastructures/services/jaeger/jaeger-v2-config.yaml`

### Grafana

**Step 1: Update Grafana environment and add labels**

In the `grafana:` service block:

1. Change env vars:
   ```yaml
   GF_SERVER_SERVE_FROM_SUB_PATH: "false"
   GF_SERVER_ROOT_URL: "http://grafana.${DOMAIN}/"
   ```

2. Remove exposed port:
   ```yaml
   # Remove:
   ports:
     - "3001:3001"
   ```

3. Add labels before `depends_on:`:
   ```yaml
   labels:
     - "traefik.enable=true"
     - "traefik.http.routers.grafana.rule=Host(`grafana.${DOMAIN}`)"
     - "traefik.http.routers.grafana.entrypoints=web"
     - "traefik.http.routers.grafana.middlewares=forward-auth"
     - "traefik.http.services.grafana.loadbalancer.server.port=3001"
   ```

### Prometheus

**Step 2: Update Prometheus command and add labels**

In the `prometheus:` service block:

1. Remove these two lines from `command:`:
   ```yaml
   # Remove:
   - --web.external-url=http://localhost/prometheus
   - --web.route-prefix=/prometheus
   ```

2. Remove exposed port:
   ```yaml
   # Remove:
   ports:
     - "9090:9090"
   ```

3. Add labels before `networks:`:
   ```yaml
   labels:
     - "traefik.enable=true"
     - "traefik.http.routers.prometheus.rule=Host(`prometheus.${DOMAIN}`)"
     - "traefik.http.routers.prometheus.entrypoints=web"
     - "traefik.http.routers.prometheus.middlewares=forward-auth"
     - "traefik.http.services.prometheus.loadbalancer.server.port=9090"
   ```

### Jaeger

**Step 3: Remove base_path from jaeger-v2-config.yaml**

In `infrastructures/services/jaeger/jaeger-v2-config.yaml`, find and remove:
```yaml
    # Sub-path /jaeger/ via nginx
    base_path: /jaeger
```

**Step 4: Add Traefik labels to Jaeger service in docker-compose**

In the `jaeger:` service block:

1. Remove exposed port:
   ```yaml
   # Remove:
   ports:
     - "16686:16686"
   ```

2. Add labels before `depends_on:`:
   ```yaml
   labels:
     - "traefik.enable=true"
     - "traefik.http.routers.jaeger.rule=Host(`jaeger.${DOMAIN}`)"
     - "traefik.http.routers.jaeger.entrypoints=web"
     - "traefik.http.routers.jaeger.middlewares=forward-auth"
     - "traefik.http.services.jaeger.loadbalancer.server.port=16686"
   ```

**Step 5: Verify**

```bash
cd infrastructures && docker compose -f docker-compose.dev.yml config --quiet
```

**Step 6: Commit**

```bash
git add infrastructures/docker-compose.dev.yml infrastructures/services/jaeger/jaeger-v2-config.yaml
git commit -m "feat(infra): route Grafana, Prometheus, Jaeger via Traefik subdomains"
```

---

## Task 7: Update Airflow services

**Files:**
- Modify: `infrastructures/docker-compose.dev.yml`

**Step 1: Update BASE_URL in all three Airflow services**

`airflow-init`, `airflow-webserver`, and `airflow-scheduler` all have:
```yaml
AIRFLOW__WEBSERVER__BASE_URL: http://localhost/airflow
```
Change to:
```yaml
AIRFLOW__WEBSERVER__BASE_URL: http://airflow.${DOMAIN}
```

**Step 2: Fix the healthcheck in airflow-webserver**

The healthcheck currently tests `http://localhost:8080/airflow/health` which relied on the sub-path. Change to:
```yaml
test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
```

**Step 3: Remove exposed port from airflow-webserver**

```yaml
# Remove:
ports:
  - "8080:8080"
```

**Step 4: Add labels to airflow-webserver**

Add before `healthcheck:`:
```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.airflow.rule=Host(`airflow.${DOMAIN}`)"
  - "traefik.http.routers.airflow.entrypoints=web"
  - "traefik.http.routers.airflow.middlewares=forward-auth"
  - "traefik.http.services.airflow.loadbalancer.server.port=8080"
```

**Step 5: Verify**

```bash
cd infrastructures && docker compose -f docker-compose.dev.yml config --quiet
```

**Step 6: Commit**

```bash
git add infrastructures/docker-compose.dev.yml
git commit -m "feat(infra): route Airflow via Traefik subdomain, fix healthcheck path"
```

---

## Task 8: Update n8n and Flower

**Files:**
- Modify: `infrastructures/docker-compose.dev.yml`

### n8n

**Step 1: Update n8n environment**

In the `n8n:` service block:

1. Remove `N8N_PATH: /n8n/`
2. Change:
   ```yaml
   WEBHOOK_URL: http://n8n.${DOMAIN}/
   N8N_EDITOR_BASE_URL: http://n8n.${DOMAIN}/
   ```

3. Remove exposed port:
   ```yaml
   # Remove:
   ports:
     - "5678:5678"
   ```

4. Add labels before `depends_on:`:
   ```yaml
   labels:
     - "traefik.enable=true"
     - "traefik.http.routers.n8n.rule=Host(`n8n.${DOMAIN}`)"
     - "traefik.http.routers.n8n.entrypoints=web"
     - "traefik.http.routers.n8n.middlewares=forward-auth"
     - "traefik.http.services.n8n.loadbalancer.server.port=5678"
   ```

### Flower

**Step 2: Update Flower command and add labels**

In the `flower:` service block:

1. Change `command` — remove `--url-prefix=flower`:
   ```yaml
   command: celery flower --broker=${CELERY_BROKER_URL} --persistent=True --db=/data/flower.db
   ```

2. Add labels before `depends_on:`:
   ```yaml
   labels:
     - "traefik.enable=true"
     - "traefik.http.routers.flower.rule=Host(`flower.${DOMAIN}`)"
     - "traefik.http.routers.flower.entrypoints=web"
     - "traefik.http.routers.flower.middlewares=forward-auth"
     - "traefik.http.services.flower.loadbalancer.server.port=5555"
   ```

**Step 3: Verify**

```bash
cd infrastructures && docker compose -f docker-compose.dev.yml config --quiet
```

**Step 4: Commit**

```bash
git add infrastructures/docker-compose.dev.yml
git commit -m "feat(infra): route n8n and Flower via Traefik subdomains"
```

---

## Task 9: Update Superset and superset_config.py

**Files:**
- Modify: `infrastructures/docker-compose.dev.yml`
- Modify: `infrastructures/services/superset/superset_config.py`

**Step 1: Add Traefik labels to superset service**

In the `superset:` service block:

1. Remove exposed port:
   ```yaml
   # Remove:
   ports:
     - "${SUPERSET_PORT:-8088}:8088"
   ```

2. Add labels before `restart:`:
   ```yaml
   labels:
     - "traefik.enable=true"
     - "traefik.http.routers.superset.rule=Host(`superset.${DOMAIN}`)"
     - "traefik.http.routers.superset.entrypoints=web"
     - "traefik.http.routers.superset.middlewares=forward-auth"
     - "traefik.http.services.superset.loadbalancer.server.port=8088"
   ```

**Step 2: Remove x_prefix from superset_config.py**

In `infrastructures/services/superset/superset_config.py`, change:

```python
# Before:
# Sub-path /superset/ via nginx
# ProxyFix legge X-Forwarded-Prefix inviato da nginx e riscrive gli URL generati
ENABLE_PROXY_FIX = True
PROXY_FIX_CONFIG = {"x_for": 1, "x_proto": 1, "x_host": 1, "x_prefix": 1}

# Nota: per SSO automatico via oauth2-proxy header "Remote-User" sarebbe necessario
# un middleware WSGI che mappi HTTP_REMOTE_USER → REMOTE_USER nell'environ.
# In dev si usa AUTH_DB (default) con login admin/admin dalla form Superset.
# La form di login è raggiungibile su /superset/login/ (nginx strippa → /login/).
```

```python
# After:
# ProxyFix legge X-Forwarded-* headers da Traefik per IP e proto corretti
ENABLE_PROXY_FIX = True
PROXY_FIX_CONFIG = {"x_for": 1, "x_proto": 1, "x_host": 1}

# In dev si usa AUTH_DB (default) con login admin/admin dalla form Superset.
# La form di login è raggiungibile su http://superset.${DOMAIN}/login/
```

**Step 3: Verify**

```bash
cd infrastructures && docker compose -f docker-compose.dev.yml config --quiet
```

**Step 4: Commit**

```bash
git add infrastructures/docker-compose.dev.yml infrastructures/services/superset/superset_config.py
git commit -m "feat(infra): route Superset via Traefik, remove sub-path ProxyFix config"
```

---

## Task 10: Update remaining monitoring services

**Files:**
- Modify: `infrastructures/docker-compose.dev.yml`

Add Traefik labels (and remove exposed ports where present) to each of these services:

**Step 1: Loki**

Remove:
```yaml
ports:
  - "3100:3100"
```

Add labels before `healthcheck:`:
```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.loki.rule=Host(`loki.${DOMAIN}`)"
  - "traefik.http.routers.loki.entrypoints=web"
  - "traefik.http.routers.loki.middlewares=forward-auth"
  - "traefik.http.services.loki.loadbalancer.server.port=3100"
```

**Step 2: Ollama**

Remove:
```yaml
ports:
  - "11434:11434"
```

Add labels before `healthcheck:`:
```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.ollama.rule=Host(`ollama.${DOMAIN}`)"
  - "traefik.http.routers.ollama.entrypoints=web"
  - "traefik.http.routers.ollama.middlewares=forward-auth"
  - "traefik.http.services.ollama.loadbalancer.server.port=11434"
```

**Step 3: cAdvisor**

Remove `--url_base_prefix=/cadvisor` from `command:`.

Remove:
```yaml
ports:
  - "8081:8080"
```

Add labels before `networks:`:
```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.cadvisor.rule=Host(`cadvisor.${DOMAIN}`)"
  - "traefik.http.routers.cadvisor.entrypoints=web"
  - "traefik.http.routers.cadvisor.middlewares=forward-auth"
  - "traefik.http.services.cadvisor.loadbalancer.server.port=8080"
```

**Step 4: Redis Exporter**

Remove:
```yaml
ports:
  - "9121:9121"
```

Add labels before `depends_on:`:
```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.redis-exporter.rule=Host(`redis-exporter.${DOMAIN}`)"
  - "traefik.http.routers.redis-exporter.entrypoints=web"
  - "traefik.http.routers.redis-exporter.middlewares=forward-auth"
  - "traefik.http.services.redis-exporter.loadbalancer.server.port=9121"
```

**Step 5: Celery Exporter**

Remove:
```yaml
ports:
  - "9808:9808"
```

Add labels before `depends_on:`:
```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.celery-exporter.rule=Host(`celery-exporter.${DOMAIN}`)"
  - "traefik.http.routers.celery-exporter.entrypoints=web"
  - "traefik.http.routers.celery-exporter.middlewares=forward-auth"
  - "traefik.http.services.celery-exporter.loadbalancer.server.port=9808"
```

**Step 6: Verify**

```bash
cd infrastructures && docker compose -f docker-compose.dev.yml config --quiet
```

**Step 7: Commit**

```bash
git add infrastructures/docker-compose.dev.yml
git commit -m "feat(infra): route Loki, Ollama, cAdvisor, exporters via Traefik subdomains"
```

---

## Task 11: Update scrapyd microservice

**Files:**
- Modify: `microservices/scraping-service/docker-compose.yml`

**Step 1: Add Traefik labels to scrapyd service**

The `scrapyd` service already joins `dev-network`. Add labels before `networks:`:

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.scrapyd.rule=Host(`scrapyd.${DOMAIN}`)"
  - "traefik.http.routers.scrapyd.entrypoints=web"
  - "traefik.http.routers.scrapyd.middlewares=forward-auth"
  - "traefik.http.services.scrapyd.loadbalancer.server.port=6800"
```

The `ports: ["6800"]` line (no host binding) can be removed — Traefik routes via the container network:
```yaml
# Remove:
ports:
  - "6800"
```

**Step 2: Verify**

```bash
cd microservices/scraping-service && docker compose config --quiet
```

**Step 3: Commit**

```bash
git add microservices/scraping-service/docker-compose.yml
git commit -m "feat(scraping): route scrapyd via Traefik at scrapyd.\${DOMAIN}"
```

---

## Task 12: Remove nginx service and config files

**Files:**
- Modify: `infrastructures/docker-compose.dev.yml`
- Delete: `infrastructures/services/nginx/nginx.conf`
- Delete: `infrastructures/services/nginx/502.html`

**Step 1: Remove the nginx service block**

Delete the entire `nginx:` service block from `docker-compose.dev.yml`:
```yaml
# Remove this entire block:
  # Nginx Reverse Proxy
  nginx:
    image: nginx:alpine
    container_name: dev-nginx
    restart: unless-stopped
    volumes:
      - ./services/nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./services/nginx/502.html:/etc/nginx/conf.d/502.html:ro
    ports:
      - "80:80"
    depends_on:
      - backoffice
      - frontend
      - oauth2-proxy
      - airflow-webserver
      - ollama
    networks:
      - dev-network
```

**Step 2: Delete nginx config directory**

```bash
rm -rf infrastructures/services/nginx/
```

**Step 3: Verify docker-compose**

```bash
cd infrastructures && docker compose -f docker-compose.dev.yml config --quiet
```

**Step 4: Commit**

```bash
git add -A
git commit -m "feat(infra): remove nginx reverse proxy (replaced by Traefik)"
```

---

## Task 13: Smoke test

**Step 1: Copy .env from .env.example if not done**

```bash
cd infrastructures
cp .env.example .env   # only if .env doesn't exist yet
# Set DOMAIN=127.0.0.1.nip.io and fill OAuth2 credentials if needed
```

**Step 2: Start the stack**

```bash
cd infrastructures
docker compose -f docker-compose.dev.yml up -d traefik oauth2-proxy postgres redis
```

Wait ~10s, then check Traefik can see all containers:
```bash
curl -s http://traefik.127.0.0.1.nip.io/api/http/routers | python3 -m json.tool | grep '"name"'
```
Expected: routers listed for each service (auth, traefik-dashboard, etc.).

**Step 3: Start remaining services**

```bash
docker compose -f docker-compose.dev.yml up -d
```

**Step 4: Verify each subdomain**

```bash
# Public services (should return 200 or redirect, not 502)
curl -I http://frontend.127.0.0.1.nip.io
curl -I http://auth.127.0.0.1.nip.io/oauth2/sign_in

# Protected services (should redirect to auth, not 502)
curl -I http://grafana.127.0.0.1.nip.io
# Expected: HTTP/1.1 302 Found  Location: http://auth.127.0.0.1.nip.io/oauth2/sign_in?rd=...

curl -I http://airflow.127.0.0.1.nip.io
curl -I http://n8n.127.0.0.1.nip.io
curl -I http://superset.127.0.0.1.nip.io
curl -I http://flower.127.0.0.1.nip.io
```

**Step 5: Verify microservice scrapyd (if stack is running)**

```bash
cd microservices/scraping-service
# Ensure DOMAIN is set (copy .env.example to .env and set DOMAIN)
docker compose up -d
curl -I http://scrapyd.127.0.0.1.nip.io
# Expected: 302 redirect to auth (ForwardAuth active)
```

**Step 6: Final commit if any tweaks were needed**

```bash
git add -A
git commit -m "fix(infra): smoke test fixes"
```
