"""
Crea i consumer API di sistema se non esistono.

Eseguire con:
    python manage.py seed_consumers

Viene anche chiamato automaticamente dopo ogni `migrate` tramite il
segnale post_migrate in api_consumers/apps.py.
"""
import os

from django.core.management.base import BaseCommand

from api_consumers.models import ApiConsumer, API_ACTIONS, API_RESOURCES


def _all_perms() -> dict[str, list[str]]:
    return {res: list(API_ACTIONS) for res in API_RESOURCES}


def _read_only_perms() -> dict[str, list[str]]:
    return {res: ["read"] for res in API_RESOURCES}


# ---------------------------------------------------------------------------
# Definizione consumer di sistema
# ---------------------------------------------------------------------------
# auth_type "jwt"     → autenticazione via Keycloak client credentials
# auth_type "api_key" → autenticazione via APISIX API Key
#
# keycloak_client_secret viene letto dall'env se disponibile,
# altrimenti usa il valore di default (stesso del realm JSON importato).
# ---------------------------------------------------------------------------

SYSTEM_CONSUMERS: list[dict] = [
    {
        "username": "scraper-service",
        "plan": "enterprise",
        "auth_type": "jwt",
        "keycloak_client_id": "scraper-service",
        "keycloak_client_secret": os.getenv(
            "KEYCLOAK_SCRAPER_CLIENT_SECRET", "scraper_secret_2026"
        ),
        "api_permissions": _all_perms(),
        "is_active": True,
        "description": "Scrapy scraping service — ingestione eventi via bulk API",
    },
    {
        "username": "airflow-service",
        "plan": "enterprise",
        "auth_type": "jwt",
        "keycloak_client_id": "airflow-service",
        "keycloak_client_secret": os.getenv(
            "KEYCLOAK_AIRFLOW_CLIENT_SECRET", "airflow_secret_2026"
        ),
        "api_permissions": _all_perms(),
        "is_active": True,
        "description": "Apache Airflow — orchestrazione DAG e trigger pipeline ETL",
    },
    {
        "username": "backoffice-admin",
        "plan": "enterprise",
        "auth_type": "jwt",
        "keycloak_client_id": "backoffice-admin",
        "keycloak_client_secret": os.getenv(
            "KEYCLOAK_BACKOFFICE_CLIENT_SECRET", "change_me_backoffice_oidc_secret"
        ),
        "api_permissions": _all_perms(),
        "is_active": True,
        "description": "Backoffice Django admin — SSO Keycloak via APISIX OIDC",
    },
]


class Command(BaseCommand):
    help = "Crea o aggiorna i consumer API di sistema (idempotente)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra cosa verrebbe fatto senza modificare il DB",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]

        for data in SYSTEM_CONSUMERS:
            username = data["username"]

            if dry_run:
                exists = ApiConsumer.objects.filter(username=username).exists()
                action = "aggiorna" if exists else "crea"
                self.stdout.write(f"  [dry-run] {action}: {username}")
                continue

            obj, created = ApiConsumer.objects.update_or_create(
                username=username,
                defaults=data,
            )
            label = self.style.SUCCESS("creato") if created else "già esistente"
            self.stdout.write(f"  {obj.username} ({obj.plan}): {label}")
