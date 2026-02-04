# Makefile for Service Events

# =============================================================================
# Variables
# =============================================================================
BACKEND_DIR := backend
FRONTEND_DIR := frontend
VENV := venv
PYTHON := $(shell pwd)/$(VENV)/bin/python3
PIP := $(shell pwd)/$(VENV)/bin/pip3

IMAGE_NAME := service-events
IMAGE_TAG := latest
CONTAINER_NAME := service-events-dev
ENV_FILE := .env

# Colori
GREEN := \033[0;32m
NC := \033[0m

.PHONY: help install build-frontend run-django dev run stop logs shell build build-no-cache clean

help:
	@echo "$(GREEN)Comandi disponibili per Service Events:$(NC)"
	@echo ""
	@echo "  Sviluppo locale:"
	@echo "    install          Installa dipendenze (pip + npm)"
	@echo "    build-frontend   Compila il frontend React (Vite build)"
	@echo "    run-django       Avvia Django localmente (caricando .env)"
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
# Sviluppo locale
# =============================================================================

install:
	@echo "$(GREEN)Installazione dipendenze Backend...$(NC)"
	@if [ ! -d $(VENV) ]; then python3 -m venv $(VENV); fi
	$(PIP) install -r $(BACKEND_DIR)/requirements.txt
	@echo "$(GREEN)Installazione dipendenze Frontend...$(NC)"
	cd $(FRONTEND_DIR) && npm install

build-frontend:
	@echo "$(GREEN)Compilazione Frontend React...$(NC)"
	cd $(FRONTEND_DIR) && npm run build
	@echo "$(GREEN)Copia build nel Backend...$(NC)"
	mkdir -p $(BACKEND_DIR)/staticfiles/frontend
	cp -r $(FRONTEND_DIR)/dist/* $(BACKEND_DIR)/staticfiles/frontend/

run-django:
	@echo "$(GREEN)Avvio Django Server locale...$(NC)"
	@if [ -f $(BACKEND_DIR)/.env ]; then \
		cd $(BACKEND_DIR) && export $$(grep -v '^#' .env | xargs) && $(PYTHON) manage.py runserver; \
	else \
		echo "File .env non trovato in $(BACKEND_DIR). Avvio senza variabili caricate da file."; \
		cd $(BACKEND_DIR) && $(PYTHON) manage.py runserver; \
	fi

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
