# Makefile — Today Events Infrastructure (docker-compose.dev.yml)

.DEFAULT_GOAL := help

# =============================================================================
# Variabili
# =============================================================================

COMPOSE := docker compose -f docker-compose.dev.yml --env-file .env

# Legge DOMAIN dal .env (default: 127.0.0.1.nip.io)
DOMAIN := $(shell grep '^DOMAIN=' .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]' || echo "127.0.0.1.nip.io")

# Harbor registry URL (per docker tag/push)
REGISTRY := registry.$(DOMAIN)

# Comando per aprire URL nel browser (macOS + Linux)
OPEN := $(shell which open 2>/dev/null || which xdg-open 2>/dev/null)

# Colori
GREEN := \033[0;32m
CYAN  := \033[0;36m
YELLOW := \033[0;33m
NC    := \033[0m

# =============================================================================
# Phony
# =============================================================================

.PHONY: help \
        up up-all down restart ps logs build pull \
        up-core up-observability up-airflow \
        logs-backoffice logs-celery logs-db logs-redis \
        logs-grafana logs-loki logs-airflow \
        logs-apisix logs-keycloak logs-tempo \
        restart-backoffice restart-celery restart-airflow \
        restart-apisix restart-keycloak restart-grafana \
        migrate makemigrations shell-django shell-db shell-redis shell-backoffice \
        create-user \
        open-admin open-flower open-grafana open-prometheus \
        open-loki open-minio open-airflow \
        open-apisix open-keycloak open-gateway open-registry \
        registry-build registry-push registry-sign registry-verify registry-ship \
        clean clean-logs

# =============================================================================
# Stack completo
# =============================================================================

up: ## Avvia lo stack di sviluppo (core + gateway + observability + minio)
	@echo "$(GREEN)Avvio stack dev...$(NC)"
	$(COMPOSE) up --build -d \
	    postgres redis \
	    etcd apisix apisix-init apisix-dashboard keycloak \
	    backoffice minio \
	    otel-collector tempo loki promtail grafana
	@echo ""
	@echo "$(CYAN)  https://backoffice.$(DOMAIN)/admin/$(NC) Django Admin"
	@echo "$(CYAN)  https://apisix-dashboard.$(DOMAIN)/$(NC) APISIX Dashboard"
	@echo "$(CYAN)  https://auth.$(DOMAIN)/$(NC)             Keycloak"
	@echo "$(CYAN)  https://grafana.$(DOMAIN)/$(NC)          Grafana"
	@echo "$(CYAN)  https://minio.$(DOMAIN)/$(NC)            MinIO Console"
	@echo ""

down: ## Ferma e rimuove tutti i container (i volumi restano)
	@echo "$(GREEN)Stop stack dev...$(NC)"
	$(COMPOSE) down

restart: ## Riavvia tutto lo stack
	@echo "$(GREEN)Riavvio stack dev...$(NC)"
	$(COMPOSE) restart

ps: ## Stato di tutti i container
	$(COMPOSE) ps

logs: ## Logs di tutti i servizi (follow)
	$(COMPOSE) logs -f

build: ## Rebuild immagini custom (backoffice)
	@echo "$(GREEN)Rebuild immagini...$(NC)"
	$(COMPOSE) build backoffice

pull: ## Aggiorna tutte le immagini Docker Hub
	@echo "$(GREEN)Pull immagini...$(NC)"
	$(COMPOSE) pull

# =============================================================================
# Avvio per gruppo
# =============================================================================
#
#   up          = core + gateway + observability + app (stack sviluppo quotidiano)
#   up-all      = tutti i servizi
#
#   Gruppi individuali:
#     up-core         stack base (postgres, redis, gateway, app, celery, harbor)
#     up-observability monitoring (prometheus, otel, tempo, loki, grafana, esportatori)
#     up-airflow      orchestrazione DAG (airflow)
#

up-core: up-harbor ## Stack base (postgres, redis, gateway, app, celery, harbor)
	@echo "$(GREEN)Avvio core...$(NC)"
	$(COMPOSE) up --build -d \
	    postgres redis \
	    etcd apisix apisix-init apisix-dashboard keycloak \
	    backoffice minio \
	    backoffice-celery-worker flower \
	    mailpit

up-harbor: ## Avvia Harbor Registry (compose separato)
	@echo "$(GREEN)Avvio Harbor Registry...$(NC)"
	docker compose -f services/harbor/docker-compose.yml up -d

up-observability: ## Monitoring (prometheus, otel, tempo, loki, promtail, grafana, esportatori)
	@echo "$(GREEN)Avvio observability...$(NC)"
	$(COMPOSE) up -d prometheus otel-collector tempo \
	    loki promtail grafana \
	    redis-exporter celery-exporter

up-airflow: ## Orchestrazione DAG (airflow webserver + scheduler)
	@echo "$(GREEN)Avvio Airflow...$(NC)"
	$(COMPOSE) up -d airflow-init airflow-webserver airflow-scheduler

up-all: up-harbor ## Avvia TUTTI i servizi (incluso Harbor)
	@echo "$(GREEN)Avvio stack completo...$(NC)"
	$(COMPOSE) up --build -d
	@echo ""
	@echo "$(CYAN)  Tutti i servizi avviati.$(NC)"
	@echo ""

# =============================================================================
# Log per servizio
# =============================================================================

logs-backoffice: ## Logs backoffice Django (follow)
	$(COMPOSE) logs -f backoffice

logs-celery: ## Logs Celery worker (follow)
	$(COMPOSE) logs -f backoffice-celery-worker

logs-db: ## Logs PostgreSQL (follow)
	$(COMPOSE) logs -f postgres

logs-redis: ## Logs Redis (follow)
	$(COMPOSE) logs -f redis

logs-grafana: ## Logs Grafana (follow)
	$(COMPOSE) logs -f grafana

logs-loki: ## Logs Loki + Promtail (follow)
	$(COMPOSE) logs -f loki promtail

logs-airflow: ## Logs Airflow webserver + scheduler (follow)
	$(COMPOSE) logs -f airflow-webserver airflow-scheduler

logs-apisix: ## Logs APISIX gateway + dashboard (follow)
	$(COMPOSE) logs -f apisix apisix-dashboard

logs-keycloak: ## Logs Keycloak IdP (follow)
	$(COMPOSE) logs -f keycloak

logs-tempo: ## Logs Grafana Tempo (follow)
	$(COMPOSE) logs -f tempo

# =============================================================================
# Restart per servizio
# =============================================================================

restart-backoffice: ## Riavvia solo il backoffice Django
	@echo "$(GREEN)Riavvio backoffice...$(NC)"
	$(COMPOSE) restart backoffice

restart-celery: ## Riavvia Celery worker
	@echo "$(GREEN)Riavvio Celery worker...$(NC)"
	$(COMPOSE) restart backoffice-celery-worker

restart-airflow: ## Riavvia Airflow webserver + scheduler
	@echo "$(GREEN)Riavvio Airflow...$(NC)"
	$(COMPOSE) restart airflow-webserver airflow-scheduler

restart-apisix: ## Riavvia APISIX gateway + etcd
	@echo "$(GREEN)Riavvio APISIX...$(NC)"
	$(COMPOSE) restart etcd apisix apisix-dashboard

restart-keycloak: ## Riavvia Keycloak IdP
	@echo "$(GREEN)Riavvio Keycloak...$(NC)"
	$(COMPOSE) restart keycloak

restart-grafana: ## Riavvia Grafana (ricarica dashboard e alert)
	@echo "$(GREEN)Riavvio Grafana...$(NC)"
	$(COMPOSE) restart grafana

# =============================================================================
# Database / Django
# =============================================================================

migrate: ## Applica migrazioni Django
	@echo "$(GREEN)Migrazioni...$(NC)"
	$(COMPOSE) exec backoffice python manage.py migrate

makemigrations: ## Crea nuove migrazioni Django
	@echo "$(GREEN)Creazione migrazioni...$(NC)"
	$(COMPOSE) exec backoffice python manage.py makemigrations

shell-django: ## Shell Django interattiva
	$(COMPOSE) exec backoffice python manage.py shell

shell-db: ## Shell psql su PostgreSQL
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER} -d $${POSTGRES_DB}

shell-redis: ## Redis CLI
	$(COMPOSE) exec redis redis-cli -a $${REDIS_PASSWORD}

shell-backoffice: ## Bash nel container backoffice
	$(COMPOSE) exec backoffice /bin/bash

# =============================================================================
# Gestione utenti Keycloak
# =============================================================================

create-user: ## Crea utente Keycloak con email di attivazione (EMAIL=x FIRST=x LAST=x ROLES="web admin")
	@if [ -z "$(EMAIL)" ] || [ -z "$(FIRST)" ] || [ -z "$(LAST)" ]; then \
	    echo "$(YELLOW)Uso: make create-user EMAIL=mario@example.com FIRST=Mario LAST=Rossi [ROLES=\"web admin\"]$(NC)"; \
	    exit 1; \
	fi
	@docker run --rm --network dev-network \
	    -e KEYCLOAK_ADMIN=$(shell grep '^KEYCLOAK_ADMIN=' .env | cut -d= -f2) \
	    -e KEYCLOAK_ADMIN_PASSWORD=$(shell grep '^KEYCLOAK_ADMIN_PASSWORD=' .env | cut -d= -f2) \
	    -v $(PWD)/scripts/kc-create-user.sh:/kc-create-user.sh:ro \
	    curlimages/curl:8.11.0 sh /kc-create-user.sh \
	    "$(EMAIL)" "$(FIRST)" "$(LAST)" $(ROLES)

# =============================================================================
# Apri nel browser
# =============================================================================

open-admin: ## Apre Django Admin  →  https://backoffice.${DOMAIN}/admin/
	@echo "$(CYAN)Apertura Django Admin...$(NC)"
	@$(OPEN) https://backoffice.$(DOMAIN)/admin/

open-flower: ## Apre Flower (Celery)  →  https://flower.${DOMAIN}/
	@echo "$(CYAN)Apertura Flower...$(NC)"
	@$(OPEN) https://flower.$(DOMAIN)/

open-grafana: ## Apre Grafana  →  https://grafana.${DOMAIN}/
	@echo "$(CYAN)Apertura Grafana...$(NC)"
	@$(OPEN) https://grafana.$(DOMAIN)/

open-prometheus: ## Apre Prometheus  →  https://prometheus.${DOMAIN}/
	@echo "$(CYAN)Apertura Prometheus...$(NC)"
	@$(OPEN) https://prometheus.$(DOMAIN)/

open-loki: ## Apre Loki (API status)  →  https://loki.${DOMAIN}/ready
	@echo "$(CYAN)Apertura Loki...$(NC)"
	@$(OPEN) https://loki.$(DOMAIN)/ready

open-minio: ## Apre MinIO Console  →  https://minio.${DOMAIN}/
	@echo "$(CYAN)Apertura MinIO Console...$(NC)"
	@$(OPEN) https://minio.$(DOMAIN)/

open-redis-exporter: ## Apre Redis Exporter  →  https://redis-exporter.${DOMAIN}/
	@echo "$(CYAN)Apertura Redis Exporter...$(NC)"
	@$(OPEN) https://redis-exporter.$(DOMAIN)/

open-airflow: ## Apre Apache Airflow  →  https://airflow.${DOMAIN}/
	@echo "$(CYAN)Apertura Airflow...$(NC)"
	@$(OPEN) https://airflow.$(DOMAIN)/

open-apisix: ## Apre APISIX Dashboard  →  https://apisix-dashboard.${DOMAIN}/
	@echo "$(CYAN)Apertura APISIX Dashboard...$(NC)"
	@$(OPEN) https://apisix-dashboard.$(DOMAIN)/

open-keycloak: ## Apre Keycloak Admin  →  https://auth.${DOMAIN}/
	@echo "$(CYAN)Apertura Keycloak Admin...$(NC)"
	@$(OPEN) https://auth.$(DOMAIN)/

open-gateway: ## Apre API Gateway  →  https://gateway.${DOMAIN}/
	@echo "$(CYAN)Apertura API Gateway...$(NC)"
	@$(OPEN) https://gateway.$(DOMAIN)/

open-registry: ## Apre Harbor Registry  →  https://registry.${DOMAIN}/
	@echo "$(CYAN)Apertura Harbor Registry...$(NC)"
	@$(OPEN) https://registry.$(DOMAIN)/

open-mail: ## Apre Mailpit  →  https://mail.${DOMAIN}/
	@echo "$(CYAN)Apertura Mailpit...$(NC)"
	@$(OPEN) https://mail.$(DOMAIN)/

# =============================================================================
# Docker Registry — build e push immagini
# =============================================================================

SCRAPING_IMAGE := $(REGISTRY)/today-events/scraping-service
COSIGN_KEY := services/harbor/cosign.key
COSIGN_PUB := services/harbor/cosign.pub

registry-build: ## Build immagine scraping-service
	@echo "$(GREEN)Build $(SCRAPING_IMAGE):latest...$(NC)"
	docker build -t $(SCRAPING_IMAGE):latest \
	    -f ../microservices/scraping-service/src/Dockerfile \
	    ../microservices/scraping-service

registry-push: ## Push immagine scraping-service sul registry
	@echo "$(GREEN)Push $(SCRAPING_IMAGE):latest...$(NC)"
	docker push $(SCRAPING_IMAGE):latest

COSIGN_SIGNING_CONFIG := services/harbor/cosign-signing-config.json

registry-sign: ## Firma l'immagine scraping-service con Cosign
	@echo "$(GREEN)Firma $(SCRAPING_IMAGE):latest...$(NC)"
	COSIGN_PASSWORD="" cosign sign --key $(COSIGN_KEY) \
	    --signing-config $(COSIGN_SIGNING_CONFIG) \
	    --allow-insecure-registry \
	    $(SCRAPING_IMAGE):latest
	@echo "$(GREEN)Immagine firmata.$(NC)"

registry-verify: ## Verifica la firma dell'immagine scraping-service
	@echo "$(GREEN)Verifica $(SCRAPING_IMAGE):latest...$(NC)"
	cosign verify --key $(COSIGN_PUB) \
	    --insecure-ignore-tlog=true \
	    --allow-insecure-registry \
	    $(SCRAPING_IMAGE):latest

registry-ship: registry-build registry-push registry-sign ## Build + push + sign in un comando
	@echo "$(GREEN)Immagine buildata, pushata e firmata.$(NC)"

# =============================================================================
# Pulizia
# =============================================================================

clean: ## Ferma lo stack e rimuove tutti i volumi dev (DISTRUTTIVO)
	@echo "$(YELLOW)Attenzione: rimozione volumi dev (dati postgres, redis, grafana...)$(NC)"
	@read -p "Continuare? [y/N] " ans && [ "$$ans" = "y" ] || exit 0
	$(COMPOSE) down -v
	@echo "$(GREEN)Stack rimosso.$(NC)"

clean-logs: ## Svuota la cartella logs/
	@echo "$(GREEN)Pulizia logs/...$(NC)"
	@find logs/ -type f ! -name '.gitkeep' -delete 2>/dev/null || true

# =============================================================================
# Help
# =============================================================================

help: ## Mostra questo messaggio di aiuto
	@echo ""
	@echo "$(GREEN)Today Events — Infrastructure Stack$(NC)"
	@echo ""
	@echo "$(CYAN)Stack completo:$(NC)"
	@grep -E '^(up|down|restart|ps|logs|build|pull):.*?## .*$$' $(MAKEFILE_LIST) \
	    | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "$(CYAN)Avvio per gruppo:$(NC)"
	@grep -E '^up-[a-z]+:.*?## .*$$' $(MAKEFILE_LIST) \
	    | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "$(CYAN)Log per servizio:$(NC)"
	@grep -E '^logs-[a-z]+:.*?## .*$$' $(MAKEFILE_LIST) \
	    | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "$(CYAN)Restart per servizio:$(NC)"
	@grep -E '^restart-[a-z]+:.*?## .*$$' $(MAKEFILE_LIST) \
	    | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "$(CYAN)Database / Django:$(NC)"
	@grep -E '^(migrate|makemigrations|shell-[a-z]+):.*?## .*$$' $(MAKEFILE_LIST) \
	    | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "$(CYAN)Apri nel browser:$(NC)"
	@grep -E '^open-[a-z]+:.*?## .*$$' $(MAKEFILE_LIST) \
	    | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "$(CYAN)Harbor Registry:$(NC)"
	@grep -E '^registry-[a-z]+:.*?## .*$$' $(MAKEFILE_LIST) \
	    | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "$(CYAN)Pulizia:$(NC)"
	@grep -E '^clean[a-z-]*:.*?## .*$$' $(MAKEFILE_LIST) \
	    | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@echo ""
