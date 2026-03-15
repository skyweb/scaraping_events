# Makefile for service-scraping (development)

.DEFAULT_GOAL := help

# =============================================================================
# Variables
# =============================================================================
SERVICE_NAME := scrapyd
CONTAINER_NAME := dev-scrapyd
COMPOSE_DEV := docker compose

# Infra stack (backoffice, postgres, redis, nginx)
INFRA_DIR := ../../infrastructures
COMPOSE_INFRA := docker compose -f $(INFRA_DIR)/docker-compose.dev.yml --env-file $(INFRA_DIR)/.env

# Local dev
SRC_DIR := src

# Spider default per test rapido
SPIDER ?= puglia_culture

# Colori
GREEN := \033[0;32m
NC := \033[0m

# =============================================================================
# Targets
# =============================================================================

.PHONY: help spiders dev dev-build dev-up dev-down dev-restart dev-logs dev-shell dev-ps \
        crawl crawl-all test infra-up infra-down infra-ps \
        clean

# =============================================================================
# Docker Compose Dev
# =============================================================================

dev: ## Build + avvia scrapyd (avvia prima infra se non attiva)
	@echo "$(GREEN)Verifico stack infra (dev-network)...$(NC)"
	@docker network inspect dev-network >/dev/null 2>&1 || $(COMPOSE_INFRA) up -d
	@echo "$(GREEN)Build + avvio scrapyd dev...$(NC)"
	$(COMPOSE_DEV) up --build -d
	@echo "$(GREEN)Scrapyd avviato: http://localhost:6800$(NC)"

dev-build: ## Build immagine dev (dopo modifiche a requirements.txt)
	$(COMPOSE_DEV) build

dev-up: ## Avvia scrapyd senza rebuild
	@docker network inspect dev-network >/dev/null 2>&1 || $(COMPOSE_INFRA) up -d
	$(COMPOSE_DEV) up -d

dev-down: ## Ferma scrapyd
	@echo "$(GREEN)Stop scrapyd...$(NC)"
	$(COMPOSE_DEV) down

dev-restart: ## Riavvia scrapyd
	$(COMPOSE_DEV) restart $(SERVICE_NAME)

dev-logs: ## Logs scrapyd (follow)
	$(COMPOSE_DEV) logs -f $(SERVICE_NAME)

dev-shell: ## Shell bash nel container scrapyd
	$(COMPOSE_DEV) exec $(SERVICE_NAME) bash

dev-ps: ## Stato container scrapyd
	$(COMPOSE_DEV) ps

# =============================================================================
# Spider info
# =============================================================================

spiders: ## Mostra elenco spider disponibili con esempi di utilizzo
	@echo ""
	@echo "$(GREEN)========== SPIDER DISPONIBILI ==========$(NC)"
	@echo ""
	@echo "$(GREEN)1. city_today$(NC) — Rete *Today.it (48 citta)"
	@echo "   Fonte: milanotoday.it, romatoday.it, bolognatoday.it, etc."
	@echo ""
	@echo "   Citta Nord:  milano, torino, genova, venezia, bologna, verona,"
	@echo "                treviso, trento, udine, pordenone, vicenza, padova,"
	@echo "                monza, lecco, sondrio, novara, brescia, parma,"
	@echo "                rimini, ravenna, forli, cesena, como, piacenza, trieste"
	@echo "   Citta Centro: roma, firenze, pisa, livorno, perugia, terni,"
	@echo "                ancona, latina, frosinone, viterbo, arezzo, pescara"
	@echo "   Citta Sud:   napoli, palermo, catania, messina, bari, foggia,"
	@echo "                salerno, avellino, reggio-calabria, lecce, brindisi,"
	@echo "                agrigento, caserta"
	@echo ""
	@echo "   Periodi: oggi, domani, weekend, questa-settimana,"
	@echo "            prossima-settimana, questo-mese"
	@echo ""
	@echo "   Esempi:"
	@echo "     make crawl SPIDER=city_today ARGS=\"-a cities=milano\""
	@echo "     make crawl SPIDER=city_today ARGS=\"-a cities=milano,roma -a periodo=weekend\""
	@echo "     make crawl SPIDER=city_today  (tutte le citta, questa settimana)"
	@echo ""
	@echo "$(GREEN)2. zero_eu$(NC) — Zero.eu (eventi culturali)"
	@echo "   Fonte: zero.eu (API REST)"
	@echo "   Citta: milano, roma, bologna, torino, firenze, venezia, napoli"
	@echo ""
	@echo "   Esempi:"
	@echo "     make crawl SPIDER=zero_eu ARGS=\"-a city=milano\""
	@echo "     make crawl SPIDER=zero_eu ARGS=\"-a city=roma\""
	@echo ""
	@echo "$(GREEN)3. artribune$(NC) — Artribune.com (mostre d'arte)"
	@echo "   Fonte: artribune.com (API WordPress REST)"
	@echo "   Copertura: tutta Italia (mostre, gallerie, musei)"
	@echo "   Parametri: max_pages, per_page (default 100)"
	@echo ""
	@echo "   Esempi:"
	@echo "     make crawl SPIDER=artribune"
	@echo "     make crawl SPIDER=artribune ARGS=\"-a max_pages=5\""
	@echo ""
	@echo "$(GREEN)========== COMANDI RAPIDI ==========$(NC)"
	@echo ""
	@echo "  make crawl SPIDER=<nome> [ARGS=\"...\"]   Lancia uno spider"
	@echo "  make crawl-all                           Lancia tutti in sequenza"
	@echo "  Output: ./data/output/"
	@echo ""

# =============================================================================
# Spider commands
# =============================================================================

DOCKER_EXEC := docker exec -i -w /app/events_scraper $(CONTAINER_NAME)

crawl: ## Lancia uno spider dal container: make crawl SPIDER=puglia_culture ARGS="-a max_pages=2"
	@echo "$(GREEN)Lancio spider: $(SPIDER)$(NC)"
	$(DOCKER_EXEC) scrapy crawl $(SPIDER) $(ARGS)

test: ## Test rapido spider (1 risultato, 1 pagina, no API, formato batch): make test [SPIDER=puglia_culture]
	@echo "$(GREEN)Test spider: $(SPIDER) (max_results=1, max_pages=1, no API)$(NC)"
	@mkdir -p data/output
	$(DOCKER_EXEC) scrapy crawl $(SPIDER) \
		-a max_pages=1 \
		-s CLOSESPIDER_ITEMCOUNT=1 \
		-s 'ITEM_PIPELINES={"pipelines.ValidationPipeline": 100, "pipelines.BatchExportPipeline": 200}' \
		$(ARGS)
	@echo "$(GREEN)Output: data/output/batch/$(NC)"

crawl-all: ## Lancia tutti gli spider in sequenza
	@echo "$(GREEN)Lancio city_today...$(NC)"
	$(DOCKER_EXEC) scrapy crawl city_today || true
	@echo "$(GREEN)Lancio zero_eu...$(NC)"
	$(DOCKER_EXEC) scrapy crawl zero_eu || true
	@echo "$(GREEN)Lancio artribune...$(NC)"
	$(DOCKER_EXEC) scrapy crawl artribune || true
	@echo "$(GREEN)Lancio puglia_culture...$(NC)"
	$(DOCKER_EXEC) scrapy crawl puglia_culture || true

# =============================================================================
# Infra stack shortcuts
# =============================================================================

infra-up: ## Avvia stack infra (postgres, redis, backoffice, nginx)
	$(COMPOSE_INFRA) up -d

infra-down: ## Ferma stack infra
	$(COMPOSE_INFRA) down

infra-ps: ## Stato stack infra
	$(COMPOSE_INFRA) ps

# =============================================================================
# Cleanup
# =============================================================================

clean: ## Rimuove container, immagini dev e file temporanei
	@echo "$(GREEN)Pulizia...$(NC)"
	-$(COMPOSE_DEV) down -v 2>/dev/null
	-rm -rf data/output/*.json data/logs/*
	-rm -rf $(SRC_DIR)/__pycache__ $(SRC_DIR)/spiders/__pycache__
	@echo "$(GREEN)Pulizia completata.$(NC)"

# =============================================================================
# Help
# =============================================================================

help: ## Mostra questo help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
