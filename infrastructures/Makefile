# Makefile — Today Events Infrastructure (docker-compose.dev.yml)

.DEFAULT_GOAL := help

# =============================================================================
# Variabili
# =============================================================================

COMPOSE := docker compose -f docker-compose.dev.yml --env-file .env

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
        logs-backoffice logs-celery logs-frontend logs-nginx logs-db logs-redis \
        logs-grafana logs-jaeger logs-loki logs-superset logs-airflow logs-oauth2 \
        logs-ollama logs-n8n \
        restart-backoffice restart-frontend restart-nginx restart-celery restart-airflow restart-oauth2 \
        restart-ollama restart-n8n \
        migrate makemigrations shell-django shell-db shell-redis shell-backoffice \
        open-admin open-flower open-grafana open-jaeger open-prometheus \
        open-superset open-loki open-airflow open-n8n \
        ollama-pull \
        clean clean-logs

# =============================================================================
# Stack completo
# =============================================================================

up: ## Avvia tutto lo stack (build immagini custom se necessario)
	@echo "$(GREEN)Avvio stack dev...$(NC)"
	$(COMPOSE) up --build -d
	@echo ""
	@echo "$(CYAN)  http://localhost/$(NC)              Frontend + API"
	@echo "$(CYAN)  http://localhost/admin/$(NC)        Django Admin"
	@echo "$(CYAN)  http://localhost/flower/$(NC)       Flower (Celery)"
	@echo "$(CYAN)  http://localhost/grafana/$(NC)      Grafana"
	@echo "$(CYAN)  http://localhost/jaeger/$(NC)       Jaeger"
	@echo "$(CYAN)  http://localhost/prometheus/$(NC)   Prometheus"
	@echo "$(CYAN)  http://localhost/superset/$(NC)     Superset"
	@echo "$(CYAN)  http://localhost/airflow/$(NC)      Airflow"
	@echo "$(CYAN)  http://localhost/n8n/$(NC)          n8n (workflow automation)"
	@echo "$(CYAN)  http://localhost/ollama/$(NC)       Ollama (LLM API)"
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

up-core: ## Avvia solo il core (postgres, redis, backoffice, celery, nginx, frontend)
	@echo "$(GREEN)Avvio core stack...$(NC)"
	$(COMPOSE) up -d postgres redis backoffice \
	    backoffice-celery-worker backoffice-celery-beat flower \
	    frontend nginx

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

up-llm: ## Avvia Ollama (LLM) + n8n (workflow automation)
	@echo "$(GREEN)Avvio LLM stack (Ollama + n8n)...$(NC)"
	$(COMPOSE) up -d ollama ollama-init n8n

# =============================================================================
# Log per servizio
# =============================================================================

logs-backoffice: ## Logs backoffice Django (follow)
	$(COMPOSE) logs -f backoffice

logs-celery: ## Logs Celery worker + beat (follow)
	$(COMPOSE) logs -f backoffice-celery-worker backoffice-celery-beat

logs-frontend: ## Logs frontend React/Vite (follow)
	$(COMPOSE) logs -f frontend

logs-nginx: ## Logs nginx (follow)
	$(COMPOSE) logs -f nginx

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

logs-ollama: ## Logs Ollama LLM (follow)
	$(COMPOSE) logs -f ollama

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

restart-nginx: ## Riavvia solo nginx (per ricaricare la config)
	@echo "$(GREEN)Riavvio nginx...$(NC)"
	$(COMPOSE) restart nginx

restart-celery: ## Riavvia worker + beat Celery
	@echo "$(GREEN)Riavvio Celery worker e beat...$(NC)"
	$(COMPOSE) restart backoffice-celery-worker backoffice-celery-beat

restart-airflow: ## Riavvia Airflow webserver + scheduler
	@echo "$(GREEN)Riavvio Airflow...$(NC)"
	$(COMPOSE) restart airflow-webserver airflow-scheduler

restart-oauth2: ## Riavvia oauth2-proxy
	@echo "$(GREEN)Riavvio oauth2-proxy...$(NC)"
	$(COMPOSE) restart oauth2-proxy

restart-ollama: ## Riavvia Ollama
	@echo "$(GREEN)Riavvio Ollama...$(NC)"
	$(COMPOSE) restart ollama

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

open-admin: ## Apre Django Admin  →  http://localhost/admin/
	@echo "$(CYAN)Apertura Django Admin...$(NC)"
	@$(OPEN) http://localhost/admin/

open-flower: ## Apre Flower (Celery)  →  http://localhost/flower/
	@echo "$(CYAN)Apertura Flower...$(NC)"
	@$(OPEN) http://localhost/flower/

open-grafana: ## Apre Grafana  →  http://localhost:3001
	@echo "$(CYAN)Apertura Grafana...$(NC)"
	@$(OPEN) http://localhost:3001

open-jaeger: ## Apre Jaeger UI  →  http://localhost:16686
	@echo "$(CYAN)Apertura Jaeger...$(NC)"
	@$(OPEN) http://localhost:16686

open-prometheus: ## Apre Prometheus  →  http://localhost:9090
	@echo "$(CYAN)Apertura Prometheus...$(NC)"
	@$(OPEN) http://localhost:9090

open-superset: ## Apre Apache Superset  →  http://localhost:8088
	@echo "$(CYAN)Apertura Superset...$(NC)"
	@$(OPEN) http://localhost:8088

open-loki: ## Apre Loki (API status)  →  http://localhost/loki/ready
	@echo "$(CYAN)Apertura Loki...$(NC)"
	@$(OPEN) http://localhost/loki/ready

open-cadvisor: ## Apre cAdvisor  →  http://localhost/cadvisor/
	@echo "$(CYAN)Apertura cAdvisor...$(NC)"
	@$(OPEN) http://localhost/cadvisor/

open-redis-exporter: ## Apre Redis Exporter  →  http://localhost/redis-exporter/
	@echo "$(CYAN)Apertura Redis Exporter...$(NC)"
	@$(OPEN) http://localhost/redis-exporter/

open-airflow: ## Apre Apache Airflow  →  http://localhost/airflow/
	@echo "$(CYAN)Apertura Airflow...$(NC)"
	@$(OPEN) http://localhost/airflow/

open-n8n: ## Apre n8n workflow automation  →  http://localhost/n8n/
	@echo "$(CYAN)Apertura n8n...$(NC)"
	@$(OPEN) http://localhost/n8n/

ollama-pull: ## Scarica un modello Ollama (es: make ollama-pull MODEL=llama3.1:8b)
	@echo "$(GREEN)Pull modello Ollama: $(MODEL)...$(NC)"
	$(COMPOSE) exec ollama ollama pull $(MODEL)

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
	@echo "$(CYAN)Pulizia:$(NC)"
	@grep -E '^clean[a-z-]*:.*?## .*$$' $(MAKEFILE_LIST) \
	    | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@echo ""
