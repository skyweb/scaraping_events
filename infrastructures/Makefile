# Makefile — Today Events Infrastructure (docker-compose.dev.yml)

.DEFAULT_GOAL := help

# =============================================================================
# Variabili
# =============================================================================

COMPOSE := docker compose -f docker-compose.dev.yml --env-file .env
COMPOSE_PROD := docker compose -f docker-compose.prod.yml --env-file .env

# Legge DOMAIN dal .env (default: 127.0.0.1.nip.io)
DOMAIN := $(shell grep '^DOMAIN=' .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]' || echo "127.0.0.1.nip.io")

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
        up down restart ps logs build pull \
        up-core up-observability up-bi up-airflow up-llm \
        prod-up prod-down prod-ps prod-logs \
        logs-backoffice logs-celery logs-frontend logs-traefik logs-db logs-redis \
        logs-grafana logs-jaeger logs-loki logs-superset logs-airflow logs-oauth2 \
        logs-n8n \
        restart-backoffice restart-frontend restart-traefik restart-celery restart-airflow restart-oauth2 \
        restart-n8n \
        migrate makemigrations shell-django shell-db shell-redis shell-backoffice \
        open-admin open-flower open-grafana open-jaeger open-prometheus \
        open-superset open-loki open-airflow open-n8n open-traefik \
        clean clean-logs

# =============================================================================
# Stack completo
# =============================================================================

up: ## Avvia tutto lo stack ESCLUSO LLM (build immagini custom se necessario)
	@echo "$(GREEN)Avvio stack dev (senza LLM)...$(NC)"
	$(COMPOSE) up --build -d \
	    postgres redis docker-api-proxy traefik auth-redirect oauth2-proxy \
	    backoffice backoffice-celery-worker backoffice-celery-beat flower \
	    frontend \
	    prometheus otel-collector jaeger loki promtail grafana \
	    redis-exporter celery-exporter cadvisor \
	    superset-init superset \
	    airflow-init airflow-webserver airflow-scheduler
	@echo ""
	@echo "$(CYAN)  https://frontend.$(DOMAIN)/$(NC)         Frontend"
	@echo "$(CYAN)  https://backoffice.$(DOMAIN)/admin/$(NC) Django Admin"
	@echo "$(CYAN)  https://flower.$(DOMAIN)/$(NC)           Flower (Celery)"
	@echo "$(CYAN)  https://grafana.$(DOMAIN)/$(NC)          Grafana"
	@echo "$(CYAN)  https://jaeger.$(DOMAIN)/$(NC)           Jaeger"
	@echo "$(CYAN)  https://prometheus.$(DOMAIN)/$(NC)       Prometheus"
	@echo "$(CYAN)  https://superset.$(DOMAIN)/$(NC)         Superset"
	@echo "$(CYAN)  https://airflow.$(DOMAIN)/$(NC)          Airflow"
	@echo "$(CYAN)  https://traefik.$(DOMAIN)/$(NC)          Traefik dashboard"
	@echo ""
	@echo "$(YELLOW)  LLM stack non avviato. Usa 'make up-llm' per:$(NC)"
	@echo "$(YELLOW)    https://n8n.$(DOMAIN)/$(NC)              n8n (workflow automation)"
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

build: ## Rebuild immagini custom (backoffice, frontend)
	@echo "$(GREEN)Rebuild immagini...$(NC)"
	$(COMPOSE) build backoffice frontend

pull: ## Aggiorna tutte le immagini Docker Hub
	@echo "$(GREEN)Pull immagini...$(NC)"
	$(COMPOSE) pull

# =============================================================================
# Avvio per gruppo
# =============================================================================

up-core: ## Avvia solo il core (postgres, redis, docker-api-proxy, traefik, backoffice, celery, frontend)
	@echo "$(GREEN)Avvio core stack...$(NC)"
	$(COMPOSE) up -d postgres redis docker-api-proxy traefik oauth2-proxy backoffice \
	    backoffice-celery-worker backoffice-celery-beat flower \
	    frontend

up-observability: ## Avvia solo lo stack observability (prometheus, otel, jaeger, loki, promtail, grafana, esportatori)
	@echo "$(GREEN)Avvio observability stack...$(NC)"
	$(COMPOSE) up -d prometheus otel-collector jaeger \
	    loki promtail grafana \
	    redis-exporter celery-exporter cadvisor

up-bi: ## Avvia solo Apache Superset (BI)
	@echo "$(GREEN)Avvio Superset...$(NC)"
	$(COMPOSE) up -d superset-init superset

up-airflow: ## Avvia solo Apache Airflow (webserver + scheduler)
	@echo "$(GREEN)Avvio Airflow...$(NC)"
	$(COMPOSE) up -d airflow-init airflow-webserver airflow-scheduler

up-llm: ## Avvia n8n (workflow automation)
	@echo "$(GREEN)Avvio LLM stack (n8n)...$(NC)"
	$(COMPOSE) up -d n8n
	@echo ""
	@echo "$(CYAN)  https://n8n.$(DOMAIN)/$(NC)              n8n (workflow automation)"
	@echo ""

# =============================================================================
# Log per servizio
# =============================================================================

logs-backoffice: ## Logs backoffice Django (follow)
	$(COMPOSE) logs -f backoffice

logs-celery: ## Logs Celery worker + beat (follow)
	$(COMPOSE) logs -f backoffice-celery-worker backoffice-celery-beat

logs-frontend: ## Logs frontend React/Vite (follow)
	$(COMPOSE) logs -f frontend

logs-traefik: ## Logs Traefik (follow)
	$(COMPOSE) logs -f traefik

logs-db: ## Logs PostgreSQL (follow)
	$(COMPOSE) logs -f postgres

logs-redis: ## Logs Redis (follow)
	$(COMPOSE) logs -f redis

logs-grafana: ## Logs Grafana (follow)
	$(COMPOSE) logs -f grafana

logs-jaeger: ## Logs Jaeger (follow)
	$(COMPOSE) logs -f jaeger

logs-loki: ## Logs Loki + Promtail (follow)
	$(COMPOSE) logs -f loki promtail

logs-superset: ## Logs Superset (follow)
	$(COMPOSE) logs -f superset

logs-airflow: ## Logs Airflow webserver + scheduler (follow)
	$(COMPOSE) logs -f airflow-webserver airflow-scheduler

logs-oauth2: ## Logs oauth2-proxy (follow)
	$(COMPOSE) logs -f oauth2-proxy

logs-n8n: ## Logs n8n workflow automation (follow)
	$(COMPOSE) logs -f n8n

# =============================================================================
# Restart per servizio
# =============================================================================

restart-backoffice: ## Riavvia solo il backoffice Django
	@echo "$(GREEN)Riavvio backoffice...$(NC)"
	$(COMPOSE) restart backoffice

restart-frontend: ## Riavvia solo il frontend
	@echo "$(GREEN)Riavvio frontend...$(NC)"
	$(COMPOSE) restart frontend

restart-traefik: ## Riavvia solo Traefik
	@echo "$(GREEN)Riavvio Traefik...$(NC)"
	$(COMPOSE) restart traefik

restart-celery: ## Riavvia worker + beat Celery
	@echo "$(GREEN)Riavvio Celery worker e beat...$(NC)"
	$(COMPOSE) restart backoffice-celery-worker backoffice-celery-beat

restart-airflow: ## Riavvia Airflow webserver + scheduler
	@echo "$(GREEN)Riavvio Airflow...$(NC)"
	$(COMPOSE) restart airflow-webserver airflow-scheduler

restart-oauth2: ## Riavvia oauth2-proxy
	@echo "$(GREEN)Riavvio oauth2-proxy...$(NC)"
	$(COMPOSE) restart oauth2-proxy

restart-n8n: ## Riavvia n8n
	@echo "$(GREEN)Riavvio n8n...$(NC)"
	$(COMPOSE) restart n8n

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

open-jaeger: ## Apre Jaeger UI  →  https://jaeger.${DOMAIN}/
	@echo "$(CYAN)Apertura Jaeger...$(NC)"
	@$(OPEN) https://jaeger.$(DOMAIN)/

open-prometheus: ## Apre Prometheus  →  https://prometheus.${DOMAIN}/
	@echo "$(CYAN)Apertura Prometheus...$(NC)"
	@$(OPEN) https://prometheus.$(DOMAIN)/

open-superset: ## Apre Apache Superset  →  https://superset.${DOMAIN}/
	@echo "$(CYAN)Apertura Superset...$(NC)"
	@$(OPEN) https://superset.$(DOMAIN)/

open-loki: ## Apre Loki (API status)  →  https://loki.${DOMAIN}/ready
	@echo "$(CYAN)Apertura Loki...$(NC)"
	@$(OPEN) https://loki.$(DOMAIN)/ready

open-cadvisor: ## Apre cAdvisor  →  https://cadvisor.${DOMAIN}/
	@echo "$(CYAN)Apertura cAdvisor...$(NC)"
	@$(OPEN) https://cadvisor.$(DOMAIN)/

open-redis-exporter: ## Apre Redis Exporter  →  https://redis-exporter.${DOMAIN}/
	@echo "$(CYAN)Apertura Redis Exporter...$(NC)"
	@$(OPEN) https://redis-exporter.$(DOMAIN)/

open-airflow: ## Apre Apache Airflow  →  https://airflow.${DOMAIN}/
	@echo "$(CYAN)Apertura Airflow...$(NC)"
	@$(OPEN) https://airflow.$(DOMAIN)/

open-n8n: ## Apre n8n workflow automation  →  https://n8n.${DOMAIN}/
	@echo "$(CYAN)Apertura n8n...$(NC)"
	@$(OPEN) https://n8n.$(DOMAIN)/

open-traefik: ## Apre Traefik dashboard  →  https://traefik.${DOMAIN}/
	@echo "$(CYAN)Apertura Traefik dashboard...$(NC)"
	@$(OPEN) https://traefik.$(DOMAIN)/

# =============================================================================
# Produzione (HTTPS — Let's Encrypt)
# =============================================================================

prod-up: ## Avvia stack PRODUZIONE con HTTPS (Let's Encrypt)
	@echo "$(GREEN)Avvio stack prod (HTTPS)...$(NC)"
	$(COMPOSE_PROD) up --build -d
	@echo ""
	@echo "$(CYAN)  https://frontend.$(DOMAIN)/$(NC)         Frontend"
	@echo "$(CYAN)  https://backoffice.$(DOMAIN)/admin/$(NC) Django Admin"
	@echo "$(CYAN)  https://flower.$(DOMAIN)/$(NC)           Flower (Celery)"
	@echo "$(CYAN)  https://grafana.$(DOMAIN)/$(NC)          Grafana"
	@echo "$(CYAN)  https://jaeger.$(DOMAIN)/$(NC)           Jaeger"
	@echo "$(CYAN)  https://prometheus.$(DOMAIN)/$(NC)       Prometheus"
	@echo "$(CYAN)  https://superset.$(DOMAIN)/$(NC)         Superset"
	@echo "$(CYAN)  https://airflow.$(DOMAIN)/$(NC)          Airflow"
	@echo "$(CYAN)  https://traefik.$(DOMAIN)/$(NC)          Traefik dashboard"
	@echo ""

prod-down: ## Ferma stack produzione (i volumi restano)
	@echo "$(GREEN)Stop stack prod...$(NC)"
	$(COMPOSE_PROD) down

prod-ps: ## Stato container produzione
	$(COMPOSE_PROD) ps

prod-logs: ## Logs produzione (follow)
	$(COMPOSE_PROD) logs -f

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
	@echo "$(CYAN)Produzione (HTTPS):$(NC)"
	@grep -E '^prod-[a-z]+:.*?## .*$$' $(MAKEFILE_LIST) \
	    | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "$(CYAN)Pulizia:$(NC)"
	@grep -E '^clean[a-z-]*:.*?## .*$$' $(MAKEFILE_LIST) \
	    | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@echo ""
