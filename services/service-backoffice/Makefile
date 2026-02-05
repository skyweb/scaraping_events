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

# Colori
GREEN := \033[0;32m
NC := \033[0m

.PHONY: help install venv build-frontend run-django migrate makemigrations \
        createsuperuser superuser collectstatic check-db shell-django \
        dev run stop logs shell build build-no-cache clean

help:
	@echo "$(GREEN)Comandi disponibili per Service Events:$(NC)"
	@echo ""
	@echo "  Setup:"
	@echo "    venv             Crea virtualenv Python in $(VENV)"
	@echo "    install          Installa dipendenze (pip + npm)"
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
	@echo "  Docker Development:"
	@echo "    dev              Avvia container in background (con volume mount)"
	@echo "    run              Avvia container in foreground"
	@echo "    stop             Ferma e rimuove container"
	@echo "    logs             Mostra logs del container"
	@echo "    shell            Apre shell nel container"
	@echo ""
	@echo "  Docker Production:"
	@echo "    build            Build immagine Docker"
	@echo "    build-no-cache   Build immagine Docker senza cache"
	@echo ""
	@echo "  Cleanup:"
	@echo "    clean            Rimuove file temporanei, container e immagine"
	@echo ""

# =============================================================================
# Setup
# =============================================================================

venv:
	@if [ ! -d $(VENV) ]; then \
		echo "$(GREEN)Creazione virtualenv in $(VENV)...$(NC)"; \
		python3.11 -m venv $(VENV); \
	else \
		echo "Virtualenv $(VENV) gia' esistente."; \
	fi

install: venv
	@echo "$(GREEN)Installazione dipendenze Backend...$(NC)"
	$(PIP) install -r $(BACKEND_DIR)/requirements.txt
	@echo "$(GREEN)Installazione dipendenze Frontend...$(NC)"
	cd $(FRONTEND_DIR) && npm install

# =============================================================================
# Django
# =============================================================================

run-django:
	@echo "$(GREEN)Avvio Django Server locale...$(NC)"
	@if [ -f $(ENV_FILE) ]; then \
		set -a && . ./$(ENV_FILE) && set +a && \
		cd $(BACKEND_DIR) && $(PYTHON) manage.py runserver; \
	else \
		echo "File $(ENV_FILE) non trovato. Avvio senza variabili caricate da file."; \
		cd $(BACKEND_DIR) && $(PYTHON) manage.py runserver; \
	fi

migrate:
	@echo "$(GREEN)Applicazione migrazioni...$(NC)"
	@set -a && . ./$(ENV_FILE) && set +a && \
	cd $(BACKEND_DIR) && $(PYTHON) manage.py migrate

makemigrations:
	@echo "$(GREEN)Creazione migrazioni...$(NC)"
	@set -a && . ./$(ENV_FILE) && set +a && \
	cd $(BACKEND_DIR) && $(PYTHON) manage.py makemigrations

createsuperuser:
	@echo "$(GREEN)Creazione superuser (interattivo)...$(NC)"
	@set -a && . ./$(ENV_FILE) && set +a && \
	cd $(BACKEND_DIR) && $(PYTHON) manage.py createsuperuser

superuser:
	@echo "$(GREEN)Creazione superuser da .env...$(NC)"
	@set -a && . ./$(ENV_FILE) && set +a && \
	cd $(BACKEND_DIR) && $(PYTHON) manage.py createsuperuser --noinput

collectstatic:
	@echo "$(GREEN)Raccolta file statici...$(NC)"
	@set -a && . ./$(ENV_FILE) && set +a && \
	cd $(BACKEND_DIR) && $(PYTHON) manage.py collectstatic --noinput

shell-django:
	@set -a && . ./$(ENV_FILE) && set +a && \
	cd $(BACKEND_DIR) && $(PYTHON) manage.py shell

check-db:
	@echo "$(GREEN)Verifica connessione DB e conteggio record...$(NC)"
	@set -a && . ./$(ENV_FILE) && set +a && \
	cd $(BACKEND_DIR) && $(PYTHON) manage.py shell -c "\
from events.models import ProductionEvent, StagingEvent; \
from etl.models import EtlRun, EtlError; \
print('=== Database Status ==='); \
print(f'Production events: {ProductionEvent.objects.count()}'); \
print(f'Staging events:    {StagingEvent.objects.count()}'); \
print(f'ETL runs:          {EtlRun.objects.count()}'); \
print(f'ETL errors:        {EtlError.objects.count()}'); \
print(); \
from django.db import connection; \
cursor = connection.cursor(); \
cursor.execute(\"SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema IN ('events_data', 'comuni_italiani', 'public') AND table_type='BASE TABLE' ORDER BY table_schema, table_name\"); \
print('=== Tabelle DB ==='); \
for row in cursor.fetchall(): print(f'  {row[0]}.{row[1]}'); \
"

# =============================================================================
# Frontend
# =============================================================================

build-frontend:
	@echo "$(GREEN)Compilazione Frontend React...$(NC)"
	cd $(FRONTEND_DIR) && npm run build
	@echo "$(GREEN)Copia build nel Backend...$(NC)"
	mkdir -p $(BACKEND_DIR)/staticfiles/frontend
	cp -r $(FRONTEND_DIR)/dist/* $(BACKEND_DIR)/staticfiles/frontend/

# =============================================================================
# Docker Development
# =============================================================================

dev:
	@echo "$(GREEN)Avvio $(CONTAINER_NAME) in development mode...$(NC)"
	docker run -d \
		--name $(CONTAINER_NAME) \
		--env-file $(ENV_FILE) \
		-p 8000:8000 \
		-v $(PWD)/$(BACKEND_DIR):/app \
		-v $(PWD)/$(FRONTEND_DIR):/app/frontend \
		$(IMAGE_NAME):$(IMAGE_TAG)
	@echo "$(GREEN)Container avviato. Accedi a http://localhost:8000$(NC)"

run:
	@echo "$(GREEN)Avvio $(CONTAINER_NAME)...$(NC)"
	docker run --rm \
		--name $(CONTAINER_NAME) \
		--env-file $(ENV_FILE) \
		-p 8000:8000 \
		$(IMAGE_NAME):$(IMAGE_TAG)

stop:
	@echo "$(GREEN)Stop $(CONTAINER_NAME)...$(NC)"
	-docker stop $(CONTAINER_NAME)
	-docker rm $(CONTAINER_NAME)
	@echo "$(GREEN)Container fermato.$(NC)"

logs:
	docker logs -f $(CONTAINER_NAME)

shell:
	docker exec -it $(CONTAINER_NAME) /bin/bash

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
	-docker stop $(CONTAINER_NAME) 2>/dev/null
	-docker rm $(CONTAINER_NAME) 2>/dev/null
	-docker rmi $(IMAGE_NAME):$(IMAGE_TAG) 2>/dev/null
	@echo "$(GREEN)Pulizia completata.$(NC)"
