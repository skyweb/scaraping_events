from django.apps import AppConfig


class ApiConsumersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api_consumers"
    verbose_name = "API Consumers"

    def ready(self) -> None:
        from django.db.models.signals import post_migrate
        post_migrate.connect(_seed_consumers, sender=self)


def _seed_consumers(sender, **kwargs) -> None:
    """Eseguito dopo ogni migrate — crea i consumer di sistema se mancano."""
    from django.core.management import call_command
    call_command("seed_consumers", verbosity=0)
