from django.db import models
from django.utils import timezone


AUTH_TYPE_CHOICES = [
    ("api_key", "API Key (APISIX)"),
    ("jwt", "JWT (Keycloak)"),
]

PLAN_CHOICES = [
    ("free", "Free"),
    ("enterprise", "Enterprise"),
    ("flat", "Flat"),
]

PLAN_LIMITS: dict[str, dict[str, int | None]] = {
    "free": {"daily": 100, "per_second": 10},
    "enterprise": {"daily": None, "per_second": None},
    "flat": {"daily": None, "per_second": None},
}


class ApiConsumer(models.Model):
    """Consumer API esterno con piano e credenziali sincronizzate su APISIX/Keycloak."""

    username = models.CharField(
        max_length=100, unique=True,
        help_text="Identificativo univoco del consumer",
    )
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="free")
    auth_type = models.CharField(
        max_length=10, choices=AUTH_TYPE_CHOICES, default="api_key",
        help_text="API Key: autenticazione via APISIX. JWT: client Keycloak con claim 'plan'.",
    )

    # Campi API Key (auth_type=api_key)
    api_key = models.CharField(
        max_length=255, unique=True, blank=True, null=True,
        help_text="Generata automaticamente alla creazione",
    )

    # Campi JWT/Keycloak (auth_type=jwt)
    keycloak_client_id = models.CharField(max_length=255, blank=True)
    keycloak_client_secret = models.CharField(max_length=255, blank=True)

    contact_email = models.EmailField(blank=True, help_text="Email di contatto")
    description = models.TextField(blank=True, help_text="Note interne")
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Data di scadenza. Lasciare vuoto per accesso illimitato.",
    )
    is_active = models.BooleanField(default=True)

    # Stato sincronizzazione
    apisix_synced = models.BooleanField(default=False, editable=False)
    keycloak_synced = models.BooleanField(default=False, editable=False)
    sync_error = models.TextField(blank=True, editable=False)
    last_synced_at = models.DateTimeField(null=True, blank=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "api_consumers"
        ordering = ["-created_at"]
        verbose_name = "API Consumer"
        verbose_name_plural = "API Consumers"

    def __str__(self) -> str:
        return f"{self.username} ({self.get_plan_display()})"

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return timezone.now() >= self.expires_at

    def get_daily_limit(self) -> int | None:
        return PLAN_LIMITS.get(self.plan, {}).get("daily")

    def get_requests_today(self) -> int:
        from rest_framework_tracking.models import APIRequestLog

        today = timezone.now().date()
        return APIRequestLog.objects.filter(
            username_persistent=self.username,
            requested_at__date=today,
        ).count()

    def get_requests_this_month(self) -> int:
        from rest_framework_tracking.models import APIRequestLog

        now = timezone.now()
        return APIRequestLog.objects.filter(
            username_persistent=self.username,
            requested_at__year=now.year,
            requested_at__month=now.month,
        ).count()

    def get_last_request_at(self):
        from rest_framework_tracking.models import APIRequestLog

        return (
            APIRequestLog.objects.filter(username_persistent=self.username)
            .order_by("-requested_at")
            .values_list("requested_at", flat=True)
            .first()
        )
