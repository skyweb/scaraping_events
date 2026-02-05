# Makefile for service-scraping

.DEFAULT_GOAL := help

# =============================================================================
# Variables
# =============================================================================
IMAGE_NAME := events-scraper
TAG := latest
FULL_IMAGE_NAME := $(IMAGE_NAME):$(TAG)
DOCKERFILE_DIR := src
DOCKERFILE_PATH := $(DOCKERFILE_DIR)/Dockerfile
SERVICE_NAME := scrapyd

VENV_DIR := venv
PYTHON := $(VENV_DIR)/bin/python3
PIP := $(VENV_DIR)/bin/pip3

# Colori per output
GREEN := \033[0;32m
NC := \033[0m

# =============================================================================
# Targets
# =============================================================================

.PHONY: all build build-image up down logs shell test-local clean help venv install

all: build up ## Default: build and bring up the service

build: ## Build the Docker service image using docker compose
	@echo "$(GREEN)Building Docker service image $(FULL_IMAGE_NAME)...$(NC)"
	docker compose build $(SERVICE_NAME)

build-image: ## Build the Docker image directly from Dockerfile (lower-level)
	@echo "$(GREEN)Building Docker image $(FULL_IMAGE_NAME) directly...$(NC)"
	docker build -f $(DOCKERFILE_PATH) -t $(FULL_IMAGE_NAME) .

up: ## Start the Scrapyd service in detached mode
	@echo "$(GREEN)Starting Scrapyd service...$(NC)"
	docker compose up -d $(SERVICE_NAME)

down: ## Stop and remove the Scrapyd service container
	@echo "$(GREEN)Stopping Scrapyd service...$(NC)"
	docker compose down $(SERVICE_NAME)

logs: ## Display real-time logs for the Scrapyd service
	@echo "$(GREEN)Displaying logs for $(SERVICE_NAME)...$(NC)"
	docker compose logs -f $(SERVICE_NAME)

shell: ## Get a shell inside the running Scrapyd container
	@echo "$(GREEN)Opening shell in $(SERVICE_NAME) container...$(NC)"
	docker compose exec $(SERVICE_NAME) bash

test-local: venv install ## Run a Scrapy spider locally (without Docker)
	@echo "$(GREEN)Running local Scrapy spider (city_today - milano)...$(NC)"
	cd $(DOCKERFILE_DIR) && $(PYTHON) -m scrapy crawl city_today -a cities=milano -o milano_events.json

clean: ## Remove the local Docker image and test output
	@echo "$(GREEN)Cleaning up...$(NC)"
	-docker rmi $(FULL_IMAGE_NAME) 2>/dev/null || true
	-rm -f $(DOCKERFILE_DIR)/milano_events.json
	@echo "$(GREEN)Cleanup complete.$(NC)"

# =============================================================================
# Local Development (without Docker)
# =============================================================================

venv: ## Create and activate a Python virtual environment
	@if [ ! -d $(VENV_DIR) ]; then \
		echo "$(GREEN)Creating virtualenv in $(VENV_DIR)...$(NC)"; \
		python3 -m venv $(VENV_DIR); \
	else \
		echo "Virtualenv $(VENV_DIR) already exists."; \
	fi

install: venv ## Install Python dependencies into the virtual environment
	@echo "$(GREEN)Installing Python dependencies...$(NC)"
	$(PIP) install -r $(DOCKERFILE_DIR)/requirements.txt

# =============================================================================
# Help
# =============================================================================

help: ## Display this help screen
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'