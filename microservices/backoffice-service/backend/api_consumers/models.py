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

# Risorse e azioni disponibili per la matrice permessi
API_RESOURCES = ["events", "comuni"]
API_ACTIONS = ["read", "create", "update", "delete"]

def default_api_permissions() -> dict[str, list[str]]:
    """Permessi di default: tutte le azioni su tutte le risorse."""
    return {res: list(API_ACTIONS) for res in API_RESOURCES}


class ApiConsumer(models.Model):
    """Consumer API esterno con piano e credenziali sincronizzate su APISIX/Keycloak."""

    username = models.CharField(
        max_length=100, unique=True,
        help_text="Identificativo univoco del consumer",
    )
    django_user = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='api_consumers',
        verbose_name="Utente Django",
        help_text="Utente Django proprietario di questo consumer (opzionale)",
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

    # Matrice permessi per risorsa: {"events": ["read", "create"], "comuni": ["read"]}
    api_permissions = models.JSONField(
        default=default_api_permissions,
        help_text="Permessi per risorsa e azione. Formato: {risorsa: [azioni]}",
        verbose_name="Permessi API",
    )

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
        """Restituisce username e piano del consumer."""
        return f"{self.username} ({self.get_plan_display()})"

    @property
    def is_expired(self) -> bool:
        """Verifica se il consumer ha superato la data di scadenza."""
        if self.expires_at is None:
            return False
        return timezone.now() >= self.expires_at

    def has_api_permission(self, resource: str, action: str) -> bool:
        """Verifica se il consumer ha il permesso per risorsa:azione."""
        perms = self.api_permissions or {}
        return action in perms.get(resource, [])

    def get_scopes(self) -> list[str]:
        """Restituisce la lista di scope nel formato risorsa:azione."""
        scopes: list[str] = []
        for resource, actions in (self.api_permissions or {}).items():
            for action in actions:
                scopes.append(f"{resource}:{action}")
        return scopes

    def get_daily_limit(self) -> int | None:
        """Restituisce il limite giornaliero di richieste per il piano corrente."""
        return PLAN_LIMITS.get(self.plan, {}).get("daily")

    def get_requests_today(self) -> int:
        """Conta le richieste API effettuate dal consumer nella giornata odierna."""
        from rest_framework_tracking.models import APIRequestLog

        today = timezone.now().date()
        return APIRequestLog.objects.filter(
            username_persistent=self.username,
            requested_at__date=today,
        ).count()

    def get_requests_this_month(self) -> int:
        """Conta le richieste API effettuate dal consumer nel mese corrente."""
        from rest_framework_tracking.models import APIRequestLog

        now = timezone.now()
        return APIRequestLog.objects.filter(
            username_persistent=self.username,
            requested_at__year=now.year,
            requested_at__month=now.month,
        ).count()

    def get_last_request_at(self):
        """Restituisce il timestamp dell'ultima richiesta API del consumer."""
        from rest_framework_tracking.models import APIRequestLog

        return (
            APIRequestLog.objects.filter(username_persistent=self.username)
            .order_by("-requested_at")
            .values_list("requested_at", flat=True)
            .first()
        )
