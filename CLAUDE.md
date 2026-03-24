# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Italian events aggregation platform. Scrapy spiders crawl regional tourism and culture sites, push events to a Django backoffice via REST API, which stores them in PostgreSQL (PostGIS) and exposes them to consumers.

## Repository Structure

```
microservices/
  backoffice-service/
    backend/          # Django project root (manage.py is here)
      backoffice/     # Django settings, root URLs, Celery, auth, middleware
      events/         # Core app: Event model, REST API, Celery tasks
      etl/            # ETL run/error tracking and OTel tracing
      scraping/       # ScrapingWebsite/Category/Location admin models
      cms/            # City pages CMS (public API, CKEditor)
      comuni_istat/   # Italian municipalities ISTAT data
      comuni_italiani/# Regional membership data
      ai_transform/   # Gemini/Groq AI transform to Schema.org
      nlp/            # spaCy NLP extraction tasks
      api_consumers/  # OAuth2 API consumer management (APISIX sync)
      templates/      # Django admin/report templates
  scraping-service/
    src/
      spiders/        # ~30 Scrapy spiders (one per regional tourism site)
      pipelines.py    # ValidationPipeline, BatchExportPipeline, ApiPipeline
      items.py        # EventItem definition
      settings.py     # Scrapy settings
  frontend-service/   # Vite/React frontend (largely standalone)
  scraping-comuni-service/  # Separate service for comuni data scraping
infrastructures/
  docker-compose.dev.yml  # Dev stack: PostgreSQL/PostGIS, Redis, OTel, Grafana, APISIX, Keycloak
  services/               # Config files for each infrastructure service
```

## Development Commands

All backend commands run inside Docker:

```bash
# Start dev stack
cd infrastructures && docker compose -f docker-compose.dev.yml up -d

# Run Django tests (single app)
docker exec -w /app/backend events-backoffice python manage.py test events.tests.test_staging_api

# Run tests with custom runner
docker exec -w /app/backend events-backoffice python manage.py test events.tests.test_staging_api --testrunner events.tests.runner.TableTestRunner

# Django management
docker exec -w /app/backend events-backoffice python manage.py migrate
docker exec -w /app/backend events-backoffice python manage.py shell

# Run a Scrapy spider
docker exec events-scraping scrapy crawl <spider_name>
```

Dependencies are managed via `requirements.txt` (pip), not uv. Dev tools (black, ruff) are in `requirements-dev.txt`.

## Linting & Formatting

Config in `microservices/backoffice-service/backend/pyproject.toml`.

```bash
# Format
docker exec -w /app/backend events-backoffice black .

# Lint (ruff with Django rules)
docker exec -w /app/backend events-backoffice ruff check .

# Fix auto-fixable issues
docker exec -w /app/backend events-backoffice ruff check --fix .
```

Or locally if dev deps are installed (`pip install -r requirements-dev.txt`):

```bash
cd microservices/backoffice-service/backend
black .
ruff check .
```

Ruff is configured with `DJ` (flake8-django), `F` (pyflakes), `E/W` (pycodestyle), `I` (isort), `UP` (pyupgrade). `migrations/` is excluded from all checks.

## Key Architecture

### Event Model (`events/models.py`)
Single `Event` model for both staging and production, distinguished by `status` field (`staging` | `published`). Uses PostgreSQL schema-qualified table: `events_data"."events`. Has PostGIS `PointField` for coordinates, `ArrayField` for categories, `rank_score` + `boost` for ranking.

### API Architecture
Two API surfaces with different auth:
- **Internal** (`/api/events/`, `/api/dashboard/`): Session auth or Keycloak JWT. Header versioning: `Accept: application/vnd.todayevents.v1+json`.
- **External** (`/api/v1/events/`): OAuth2 client credentials via Keycloak. URL-path versioned. Permissions matrix via `api_consumers` app: `events:read/create/update/delete`.

APISIX is the reverse proxy/API gateway. It injects `X-Consumer-Plan` header for plan-based field filtering (`PlanFieldFilterMixin`).

### Bulk Ingestion Flow
1. Scrapy `ApiPipeline` collects items into category-keyed buffers, flushes at `API_BATCH_SIZE` (default 50).
2. Each flush POSTs to `/api/v1/events/staging/bulk/`.
3. Default: async — Celery task `process_bulk_events` returns 202 with `task_id`.
4. `?sync=true`: synchronous processing, returns 201/200/400.
5. Check task status: `GET /api/v1/events/staging/bulk-status/<task_id>/`.

### Celery
Broker: Redis DB 1. Result backend: `django-db` (django_celery_results). Tasks auto-discovered. Schedule managed via `django_celery_beat` (DB scheduler).

### Observability
- OpenTelemetry: traces exported to OTel Collector → Tempo. `etl/tracing.py` provides `log_trace_event()` to write trace events to DB.
- Metrics: `django-prometheus` middleware exposes `/metrics`.
- Logs: JSON structured logging (python-json-logger) → Alloy → Loki.

### Authentication
`backoffice/authentication.py` has two backends:
- `ApisixConsumerAuthentication`: reads `X-Consumer-Plan` + consumer headers injected by APISIX.
- `KeycloakJWTAuthentication`: validates JWT against Keycloak JWKS endpoint.
Admin SSO via Keycloak OIDC through APISIX oauth2-proxy.

## Code Style

- Python 3.11 (Docker image), type hints required
- No `Any` types
- Early returns, avoid nested conditionals
- Prefer Function-Based Views
- Django admin uses `django-unfold` theme
- API docs via `drf-spectacular` (Scalar UI at `/docs/`, public schema at `/docs/public/`)

## Testing Notes

- Tests use Django's built-in test runner (not pytest)
- OAuth2 tokens created in `setUpTestData` via `api_consumers` app
- Async bulk tests mock `events.tasks.process_bulk_events` (patch at source for lazy imports inside methods) and `events.views.AsyncResult` (patch where used for top-level imports)
- Celery has no `TASK_ALWAYS_EAGER` — async dispatch must be mocked in tests
