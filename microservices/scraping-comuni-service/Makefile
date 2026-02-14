# Makefile for scraping-comuni-service

.DEFAULT_GOAL := help

# =============================================================================
# Variables
# =============================================================================
SERVICE_NAME := scraper
COMPOSE := docker compose
SPIDER := comuni_spider

# Colori
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m

# =============================================================================
# Targets
# =============================================================================

.PHONY: help crawl crawl-local crawl-docker \
        build up down logs shell ps \
        clean clean-output check-output \
        install

# =============================================================================
# Scraping (locale)
# =============================================================================

crawl: crawl-local ## Alias per crawl-local

crawl-local: ## Lancia lo spider in locale
	@echo "$(GREEN)Lancio spider comuni_spider...$(NC)"
	scrapy crawl $(SPIDER) -s LOG_LEVEL=INFO
	@echo "$(GREEN)Scraping completato. Output in data/output/$(NC)"

# =============================================================================
# Docker
# =============================================================================

build: ## Build immagine Docker
	@echo "$(GREEN)Build immagine Docker...$(NC)"
	$(COMPOSE) build

crawl-docker: build ## Lancia lo spider via Docker
	@echo "$(GREEN)Lancio spider via Docker...$(NC)"
	@docker network inspect dev-network >/dev/null 2>&1 || docker network create dev-network
	$(COMPOSE) run --rm $(SERVICE_NAME)
	@echo "$(GREEN)Scraping completato. Output in data/output/$(NC)"

up: build ## Avvia container (resta in foreground)
	@docker network inspect dev-network >/dev/null 2>&1 || docker network create dev-network
	$(COMPOSE) up

down: ## Ferma container
	$(COMPOSE) down

logs: ## Logs container (follow)
	$(COMPOSE) logs -f $(SERVICE_NAME)

shell: ## Shell bash nel container
	$(COMPOSE) run --rm $(SERVICE_NAME) bash

ps: ## Stato container
	$(COMPOSE) ps

# =============================================================================
# Setup
# =============================================================================

install: ## Installa dipendenze in locale
	pip install -r requirements.txt

# =============================================================================
# Output e pulizia
# =============================================================================

check-output: ## Mostra struttura output generata
	@echo "$(GREEN)Struttura output:$(NC)"
	@find data/output -type f -name "*.json" 2>/dev/null | sort || echo "  (nessun output)"
	@echo ""
	@echo "$(GREEN)Conteggi:$(NC)"
	@echo "  Regioni:  $$(find data/output -maxdepth 2 -name "*.json" ! -name "*_comuni*" ! -name "errori*" 2>/dev/null | wc -l | tr -d ' ')"
	@echo "  Province: $$(find data/output -maxdepth 3 -name "*.json" ! -name "*_comuni*" ! -name "errori*" -mindepth 3 2>/dev/null | wc -l | tr -d ' ')"
	@echo "  Comuni:   $$(find data/output -name "*_comuni.json" 2>/dev/null | xargs python3 -c 'import sys,json; print(sum(len(json.load(open(f))) for f in sys.argv[1:]))' 2>/dev/null || echo 0)"
	@if [ -f data/output/errori.log ]; then \
		echo ""; \
		echo "$(YELLOW)Errori: $$(python3 -c 'import json; print(len(json.load(open("data/output/errori.log"))))') trovati in data/output/errori.log$(NC)"; \
	fi

clean-output: ## Rimuove tutti i JSON generati
	@echo "$(GREEN)Pulizia output...$(NC)"
	rm -rf data/output/*/
	rm -f data/output/errori.log
	@echo "$(GREEN)Output pulito.$(NC)"

clean: clean-output ## Pulizia completa (output + cache + container)
	@echo "$(GREEN)Pulizia completa...$(NC)"
	-$(COMPOSE) down -v 2>/dev/null
	-rm -rf comuni_istat/__pycache__ comuni_istat/spiders/__pycache__
	-rm -rf .scrapy
	@echo "$(GREEN)Pulizia completata.$(NC)"

# =============================================================================
# Help
# =============================================================================

help: ## Mostra questo help
	@echo ""
	@echo "$(GREEN)Scraping Comuni Italiani$(NC)"
	@echo "Scarica dati su regioni, province e comuni da comuni-italiani.it"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Esempio rapido:$(NC)"
	@echo "  make install    # prima volta"
	@echo "  make crawl      # lancia scraping"
	@echo "  make check-output"
	@echo ""
