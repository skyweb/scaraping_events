# Makefile for Service Events

# =============================================================================
# Variables
# =============================================================================
BACKEND_DIR := backend
FRONTEND_DIR := frontend
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

.PHONY: help build-frontend \
        dev dev-build dev-up dev-down dev-restart dev-logs dev-shell \
        dev-migrate dev-makemigrations dev-superuser dev-collectstatic \
        dev-ps dev-oauth2 build build-no-cache clean

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
	@echo "  Frontend:"
	@echo "    build-frontend   Compila il frontend React (Vite build)"
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
	@echo ""
	@echo "  Docker Production:"
	@echo "    build            Build immagine Docker produzione"
	@echo "    build-no-cache   Build immagine Docker senza cache"
	@echo ""
	@echo "  Cleanup:"
	@echo "    clean            Rimuove file temporanei e stack dev"
	@echo ""

# =============================================================================
# Frontend
# =============================================================================

build-frontend:
	@echo "$(GREEN)Compilazione Frontend React...$(NC)"
	@if [ ! -d $(FRONTEND_DIR)/node_modules ]; then \
		echo "$(GREEN)Installazione dipendenze npm...$(NC)"; \
		cd $(FRONTEND_DIR) && npm install; \
	fi
	cd $(FRONTEND_DIR) && npm run build
	@echo "$(GREEN)Copia build nel Backend...$(NC)"
	mkdir -p $(BACKEND_DIR)/staticfiles/frontend
	cp -r $(FRONTEND_DIR)/dist/* $(BACKEND_DIR)/staticfiles/frontend/

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
	rm -rf $(FRONTEND_DIR)/dist
	rm -rf $(BACKEND_DIR)/__pycache__
	rm -rf $(BACKEND_DIR)/**/__pycache__
	-$(COMPOSE_DEV) down -v 2>/dev/null
	-docker rmi $(IMAGE_NAME):$(IMAGE_TAG) 2>/dev/null
	@echo "$(GREEN)Pulizia completata.$(NC)"
