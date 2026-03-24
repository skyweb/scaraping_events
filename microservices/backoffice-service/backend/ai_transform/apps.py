from django.apps import AppConfig


class AiTransformConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ai_transform"
    verbose_name = "AI Transform"

    def ready(self):
        import backoffice.spectacular_extensions  # noqa: F401
