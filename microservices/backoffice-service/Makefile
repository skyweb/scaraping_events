# Makefile for Service Events

# =============================================================================
# Variables
# =============================================================================
BACKEND_DIR := backend
VENV := $(BACKEND_DIR)/venv
PYTHON := $(shell pwd)/$(VENV)/bin/python3
PIP := $(shell pwd)/$(VENV)/bin/pip3

IMAGE_NAME := service-events
IMAGE_TAG := latest
CONTAINER_NAME := service-events-dev
ENV_FILE := .env

# Docker Compose dev
INFRA_DIR := ../../infrastructures
COMPOSE_DEV := docker compose -f $(INFRA_DIR)/docker-compose.dev.yml --env-file $(INFRA_DIR)/.env

# Colori
GREEN := \033[0;32m
NC := \033[0m

.PHONY: help \
        dev dev-build dev-up dev-down dev-restart dev-logs dev-shell \
        dev-migrate dev-makemigrations dev-superuser dev-collectstatic \
        dev-ps dev-oauth2 dev-import-comuni \
        test-events test-events-unit test-events-models test-events-db \
        test-events-api-internal test-events-api-public test-events-security \
        test-events-regression test-events-performance test-events-api-table \
        coverage-events coverage-events-html coverage-events-report coverage-events-erase \
        build build-no-cache clean

help:
	@echo "$(GREEN)Comandi disponibili per Service Events:$(NC)"
	@echo ""
	@echo ""
	@echo "  Django:"
	@echo "    run-django       Avvia Django localmente (caricando .env)"
	@echo "    migrate          Applica migrazioni database"
	@echo "    makemigrations   Crea nuove migrazioni"
	@echo "    createsuperuser  Crea superuser (interattivo)"
	@echo "    superuser        Crea superuser da variabili .env (non interattivo)"
	@echo "    collectstatic    Raccoglie file statici"
	@echo "    shell-django     Apre Django shell"
	@echo "    check-db         Verifica connessione DB e conta record"
	@echo ""
	@echo "  Docker Compose Dev (postgres, redis, django, celery, nginx):"
	@echo "    dev              Build + avvia tutto lo stack dev in background"
	@echo "    dev-build        Build immagini dev (dopo modifiche a requirements.txt)"
	@echo "    dev-up           Avvia lo stack dev (senza rebuild)"
	@echo "    dev-down         Ferma e rimuove lo stack dev"
	@echo "    dev-restart      Riavvia solo il servizio backoffice"
	@echo "    dev-logs         Mostra logs di tutti i servizi (follow)"
	@echo "    dev-shell        Apre shell bash nel container backoffice"
	@echo "    dev-ps           Mostra stato dei container dev"
	@echo "    dev-migrate      Esegue migrate dentro il container"
	@echo "    dev-makemigrations  Crea migrazioni dentro il container"
	@echo "    dev-superuser    Crea superuser dentro il container"
	@echo "    dev-collectstatic  Raccoglie file statici dentro il container"
	@echo "    dev-oauth2       Crea/mostra credenziali OAuth2 per lo scraper"
	@echo "    dev-import-comuni  Importa JSON scraping comuni nel DB (richiede DATA_DIR)"
	@echo ""
	@echo "  Test Events (dentro container dev):"
	@echo "    test-events              Esegue tutta la suite events"
	@echo "    test-events-unit         Esegue solo unit test"
	@echo "    test-events-models       Esegue solo model test"
	@echo "    test-events-db           Esegue solo database/bulk task test"
	@echo "    test-events-api-internal Esegue solo API interne"
	@echo "    test-events-api-public   Esegue solo API pubbliche"
	@echo "    test-events-security     Esegue solo security test"
	@echo "    test-events-regression   Esegue solo regression test"
	@echo "    test-events-performance  Esegue solo performance test"
	@echo "    test-events-api-table    Esegue API public con runner tabellare"
	@echo "    coverage-events         Esegue coverage della suite events"
	@echo "    coverage-events-report  Mostra report coverage testuale"
	@echo "    coverage-events-html    Genera report coverage HTML"
	@echo "    coverage-events-erase   Pulisce i dati coverage"
	@echo ""
	@echo "  Docker Production:"
	@echo "    build            Build immagine Docker produzione"
	@echo "    build-no-cache   Build immagine Docker senza cache"
	@echo ""
	@echo "  Cleanup:"
	@echo "    clean            Rimuove file temporanei e stack dev"
	@echo ""

# =============================================================================
# Docker Compose Development
# =============================================================================

dev:
	@echo "$(GREEN)Build + avvio stack dev...$(NC)"
	$(COMPOSE_DEV) up --build -d
	@echo "$(GREEN)Stack avviato. Backoffice: http://localhost:8000 | Nginx: http://localhost$(NC)"

dev-build:
	@echo "$(GREEN)Build immagini dev...$(NC)"
	$(COMPOSE_DEV) build

dev-up:
	@echo "$(GREEN)Avvio stack dev...$(NC)"
	$(COMPOSE_DEV) up -d
	@echo "$(GREEN)Stack avviato.$(NC)"

dev-down:
	@echo "$(GREEN)Stop stack dev...$(NC)"
	$(COMPOSE_DEV) down
	@echo "$(GREEN)Stack fermato.$(NC)"

dev-restart:
	@echo "$(GREEN)Riavvio backoffice...$(NC)"
	$(COMPOSE_DEV) restart backoffice

dev-logs:
	$(COMPOSE_DEV) logs -f

dev-shell:
	$(COMPOSE_DEV) exec backoffice /bin/bash

dev-ps:
	$(COMPOSE_DEV) ps

dev-migrate:
	@echo "$(GREEN)Migrazioni nel container...$(NC)"
	$(COMPOSE_DEV) exec backoffice python manage.py migrate

dev-makemigrations:
	@echo "$(GREEN)Creazione migrazioni nel container...$(NC)"
	$(COMPOSE_DEV) exec backoffice python manage.py makemigrations

dev-superuser:
	@echo "$(GREEN)Creazione superuser nel container...$(NC)"
	$(COMPOSE_DEV) exec backoffice python manage.py createsuperuser --noinput

dev-collectstatic:
	@echo "$(GREEN)Raccolta file statici nel container...$(NC)"
	$(COMPOSE_DEV) exec backoffice python manage.py collectstatic --noinput

define OAUTH2_SCRIPT
import secrets
from oauth2_provider.models import Application
plain_secret = secrets.token_urlsafe(48)
app, created = Application.objects.update_or_create(
    name='scraper-client',
    defaults={
        'client_type': Application.CLIENT_CONFIDENTIAL,
        'authorization_grant_type': Application.GRANT_CLIENT_CREDENTIALS,
        'client_secret': plain_secret,
    }
)
status = 'CREATA' if created else 'AGGIORNATA'
print()
print(f'  Applicazione: {app.name} ({status})')
print(f'  Client ID:     {app.client_id}')
print()
print('  Copia nel .env dello scraping-service:')
print()
print(f'  API_CLIENT_ID={app.client_id}')
print(f'  API_CLIENT_SECRET={plain_secret}')
print()
endef
export OAUTH2_SCRIPT

dev-oauth2:
	@echo "$(GREEN)Creazione/recupero credenziali OAuth2 per scraper...$(NC)"
	@echo "$$OAUTH2_SCRIPT" | $(COMPOSE_DEV) exec -T backoffice python manage.py shell

# =============================================================================
# Importazione dati scraping comuni
# =============================================================================

SCRAPING_COMUNI_OUTPUT := ../scraping-comuni-service/data/output
CONTAINER_IMPORT_PATH := /tmp/scraping_output

dev-import-comuni: ## Importa JSON scraping comuni nel DB (--flush opzionale)
	@echo "$(GREEN)Copia JSON nel container dev-backoffice...$(NC)"
	@if [ ! -d "$(SCRAPING_COMUNI_OUTPUT)" ]; then \
		echo "Errore: directory $(SCRAPING_COMUNI_OUTPUT) non trovata"; \
		echo "Lancia prima 'make crawl' nel scraping-comuni-service"; \
		exit 1; \
	fi
	docker cp $(SCRAPING_COMUNI_OUTPUT) dev-backoffice:$(CONTAINER_IMPORT_PATH)
	@echo "$(GREEN)Importazione in corso...$(NC)"
	$(COMPOSE_DEV) exec backoffice python manage.py import_scraping_comuni $(CONTAINER_IMPORT_PATH) $(FLUSH)
	@echo "$(GREEN)Pulizia file temporanei nel container...$(NC)"
	$(COMPOSE_DEV) exec backoffice rm -rf $(CONTAINER_IMPORT_PATH)
	@echo "$(GREEN)Importazione completata.$(NC)"

# =============================================================================
# Test suite events
# =============================================================================

test-events:
	@echo "$(GREEN)Esecuzione suite events completa...$(NC)"
	$(COMPOSE_DEV) exec backoffice python manage.py test events.tests

test-events-unit:
	@echo "$(GREEN)Esecuzione unit test events...$(NC)"
	$(COMPOSE_DEV) exec backoffice python manage.py test events.tests.unit

test-events-models:
	@echo "$(GREEN)Esecuzione model test events...$(NC)"
	$(COMPOSE_DEV) exec backoffice python manage.py test events.tests.models

test-events-db:
	@echo "$(GREEN)Esecuzione database test events...$(NC)"
	$(COMPOSE_DEV) exec backoffice python manage.py test events.tests.database

test-events-api-internal:
	@echo "$(GREEN)Esecuzione API interne events...$(NC)"
	$(COMPOSE_DEV) exec backoffice python manage.py test events.tests.api.internal

test-events-api-public:
	@echo "$(GREEN)Esecuzione API pubbliche events...$(NC)"
	$(COMPOSE_DEV) exec backoffice python manage.py test events.tests.api.public

test-events-security:
	@echo "$(GREEN)Esecuzione security test events...$(NC)"
	$(COMPOSE_DEV) exec backoffice python manage.py test events.tests.security

test-events-regression:
	@echo "$(GREEN)Esecuzione regression test events...$(NC)"
	$(COMPOSE_DEV) exec backoffice python manage.py test events.tests.regression

test-events-performance:
	@echo "$(GREEN)Esecuzione performance test events...$(NC)"
	$(COMPOSE_DEV) exec backoffice python manage.py test events.tests.performance

test-events-api-table:
	@echo "$(GREEN)Esecuzione API public events con runner tabellare...$(NC)"
	$(COMPOSE_DEV) exec backoffice python manage.py test events.tests.api.public --testrunner events.tests.runner.TableTestRunner

coverage-events:
	@echo "$(GREEN)Esecuzione coverage suite events...$(NC)"
	$(COMPOSE_DEV) exec backoffice coverage run --rcfile=/app/backend/.coveragerc manage.py test events.tests

coverage-events-report:
	@echo "$(GREEN)Report coverage suite events...$(NC)"
	$(COMPOSE_DEV) exec backoffice coverage report --rcfile=/app/backend/.coveragerc -m

coverage-events-html:
	@echo "$(GREEN)Generazione coverage HTML suite events...$(NC)"
	$(COMPOSE_DEV) exec backoffice coverage html --rcfile=/app/backend/.coveragerc
	@echo "$(GREEN)Report HTML disponibile in backend/htmlcov/index.html$(NC)"

coverage-events-erase:
	@echo "$(GREEN)Pulizia dati coverage...$(NC)"
	$(COMPOSE_DEV) exec backoffice coverage erase

# =============================================================================
# Docker Production
# =============================================================================

build:
	@echo "$(GREEN)Building $(IMAGE_NAME):$(IMAGE_TAG) per produzione...$(NC)"
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .
	@echo "$(GREEN)Immagine $(IMAGE_NAME):$(IMAGE_TAG) creata.$(NC)"

build-no-cache:
	@echo "$(GREEN)Building $(IMAGE_NAME):$(IMAGE_TAG) (no cache)...$(NC)"
	docker build --no-cache -t $(IMAGE_NAME):$(IMAGE_TAG) .
	@echo "$(GREEN)Immagine $(IMAGE_NAME):$(IMAGE_TAG) creata.$(NC)"

# =============================================================================
# Cleanup
# =============================================================================

clean:
	@echo "$(GREEN)Pulizia...$(NC)"
	rm -rf $(BACKEND_DIR)/__pycache__
	rm -rf $(BACKEND_DIR)/**/__pycache__
	-$(COMPOSE_DEV) down -v 2>/dev/null
	-docker rmi $(IMAGE_NAME):$(IMAGE_TAG) 2>/dev/null
	@echo "$(GREEN)Pulizia completata.$(NC)"
