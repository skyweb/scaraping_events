import logging
import os
import secrets

from django.contrib import admin, messages

logger = logging.getLogger(__name__)
from django.utils import timezone
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from .models import ApiConsumer
from .services import (
    delete_client_from_keycloak,
    delete_consumer_from_apisix,
    sync_consumer_to_apisix,
    sync_consumer_to_keycloak,
)

DOMAIN = os.environ.get("DOMAIN", "127.0.0.1.nip.io")
API_BASE = f"https://backoffice.{DOMAIN}/api/external/v1/staging/"
TOKEN_URL = f"https://auth.{DOMAIN}/realms/today-events/protocol/openid-connect/token"

# Stile condiviso per i blocchi curl
_CODE_STYLE = (
    "background:#1e1e2e; color:#cdd6f4; padding:16px 20px; border-radius:8px;"
    " font-family:'JetBrains Mono',monospace; font-size:13px; line-height:1.6;"
    " white-space:pre-wrap; word-break:break-all; display:block; margin:8px 0;"
    " border:1px solid #45475a;"
)
_COMMENT_COLOR = "#6c7086"
_FLAG_COLOR = "#89b4fa"
_STRING_COLOR = "#a6e3a1"
_LABEL_STYLE = (
    "display:inline-block; padding:3px 10px; border-radius:4px; font-size:11px;"
    " font-weight:600; letter-spacing:0.5px; margin-bottom:6px;"
)


def _curl_box(label: str, label_bg: str, curl: str) -> str:
    """Genera un blocco HTML con label + curl syntax-highlighted."""
    return (
        f'<span style="{_LABEL_STYLE} background:{label_bg}; color:#fff;">'
        f"{label}</span>"
        f'<code style="{_CODE_STYLE}">{curl}</code>'
    )


@admin.register(ApiConsumer)
class ApiConsumerAdmin(ModelAdmin):
    list_display = [
        "username", "plan", "auth_type", "is_active",
        "show_expiry_status", "show_sync_status", "show_requests_today", "created_at",
    ]
    list_filter = ["plan", "auth_type", "is_active", "apisix_synced", "keycloak_synced"]
    search_fields = ["username", "contact_email", "description"]
    actions = ["sync_selected_to_gateway", "regenerate_api_keys"]

    fieldsets = [
        ("Configurazione", {
            "classes": ["tab"],
            "fields": [
                "username", "plan", "auth_type", "is_active",
                "expires_at", "contact_email", "description",
            ],
        }),
        ("Credenziali API Key", {
            "classes": ["tab"],
            "description": "Per auth_type = API Key. La chiave viene generata automaticamente.",
            "fields": ["api_key"],
        }),
        ("Credenziali JWT (Keycloak)", {
            "classes": ["tab"],
            "description": "Per auth_type = JWT. Il client Keycloak viene creato automaticamente.",
            "fields": ["keycloak_client_id", "keycloak_client_secret"],
        }),
        ("Stato sincronizzazione", {
            "classes": ["tab"],
            "fields": ["apisix_synced", "keycloak_synced", "sync_error", "last_synced_at"],
        }),
        ("Utilizzo", {
            "classes": ["tab"],
            "fields": [
                "show_usage_today", "show_usage_month", "show_last_request",
            ],
        }),
        ("Esempio chiamata", {
            "classes": ["tab"],
            "fields": ["show_curl_example"],
        }),
    ]

    def get_readonly_fields(self, request, obj=None):
        base = [
            "apisix_synced", "keycloak_synced", "sync_error", "last_synced_at",
            "show_usage_today", "show_usage_month", "show_last_request",
            "show_curl_example",
        ]
        if obj:
            return [*base, "username", "api_key", "keycloak_client_id", "keycloak_client_secret"]
        return [*base, "api_key", "keycloak_client_secret"]

    # ── Display methods ──────────────────────────────────────────────────

    @admin.display(description="Scadenza")
    def show_expiry_status(self, obj: ApiConsumer) -> str:
        if obj.expires_at is None:
            return "Mai"
        if obj.is_expired:
            return format_html(
                '<span style="color:#e64553; font-weight:600">Scaduto ({})</span>',
                obj.expires_at.strftime("%d/%m/%Y"),
            )
        return obj.expires_at.strftime("%d/%m/%Y %H:%M")

    @admin.display(description="Sync", boolean=True)
    def show_sync_status(self, obj: ApiConsumer) -> bool:
        if obj.auth_type == "api_key":
            return obj.apisix_synced
        return obj.keycloak_synced

    @admin.display(description="Req oggi")
    def show_requests_today(self, obj: ApiConsumer) -> str:
        count = obj.get_requests_today()
        limit = obj.get_daily_limit()
        if limit:
            return f"{count} / {limit}"
        return str(count)

    @admin.display(description="Utilizzo oggi")
    def show_usage_today(self, obj: ApiConsumer) -> str:
        count = obj.get_requests_today()
        limit = obj.get_daily_limit()
        if limit:
            pct = min(100, round(count / limit * 100, 1))
            return f"{count} / {limit} richieste ({pct}%)"
        return f"{count} richieste (illimitate)"

    @admin.display(description="Utilizzo mese")
    def show_usage_month(self, obj: ApiConsumer) -> str:
        return f"{obj.get_requests_this_month()} richieste"

    @admin.display(description="Ultima richiesta")
    def show_last_request(self, obj: ApiConsumer) -> str:
        last = obj.get_last_request_at()
        if last:
            return last.strftime("%d/%m/%Y %H:%M:%S")
        return "Nessuna richiesta"

    @admin.display(description="Esempio chiamata cURL")
    def show_curl_example(self, obj: ApiConsumer) -> str:
        if not obj.pk:
            return "Salva il consumer per generare l'esempio."

        c = f'<span style="color:{_COMMENT_COLOR}">'  # comment open
        f = f'<span style="color:{_FLAG_COLOR}">'      # flag open
        s = f'<span style="color:{_STRING_COLOR}">'     # string open
        e = "</span>"                                    # close

        if obj.auth_type == "api_key":
            if not obj.api_key:
                return "API key non ancora generata."

            curl = (
                f'{c}# Chiamata diretta con API Key{e}\n'
                f'curl {f}-H{e} {s}"apikey: {obj.api_key}"{e} \\\n'
                f"     {s}{API_BASE}{e}"
            )
            return format_html(_curl_box("API KEY", "#45475a", curl))

        # JWT flow: token exchange + API call
        client_id = obj.keycloak_client_id or f"api-{obj.username}"
        raw_secret = obj.keycloak_client_secret
        if raw_secret and len(raw_secret) > 8:
            client_secret = f"{raw_secret[:4]}...{raw_secret[-4:]}"
        elif raw_secret:
            client_secret = "****"
        else:
            client_secret = "&lt;in attesa di sync Keycloak&gt;"

        curl_token = (
            f'{c}# 1. Ottieni access token{e}\n'
            f"curl {f}-s{e} {f}-X POST{e} {s}{TOKEN_URL}{e} \\\n"
            f'     {f}-d{e} {s}"grant_type=client_credentials"{e} \\\n'
            f'     {f}-d{e} {s}"client_id={client_id}"{e} \\\n'
            f'     {f}-d{e} {s}"client_secret={client_secret}"{e}'
        )

        curl_api = (
            f'{c}# 2. Chiama le API con il token{e}\n'
            f'curl {f}-H{e} {s}"Authorization: Bearer $TOKEN"{e} \\\n'
            f"     {s}{API_BASE}{e}"
        )

        # One-liner combinato
        curl_oneliner = (
            f'{c}# Oppure in un unico comando:{e}\n'
            f"TOKEN=$(curl {f}-s{e} {f}-X POST{e} {s}{TOKEN_URL}{e} \\\n"
            f'  {f}-d{e} {s}"grant_type=client_credentials"{e} \\\n'
            f'  {f}-d{e} {s}"client_id={client_id}"{e} \\\n'
            f'  {f}-d{e} {s}"client_secret={client_secret}"{e} \\\n'
            f"  | python3 {f}-c{e} {s}\"import sys,json; print(json.load(sys.stdin)['access_token'])\"{e})\n"
            f"\n"
            f'curl {f}-H{e} {s}"Authorization: Bearer $TOKEN"{e} {s}{API_BASE}{e}'
        )

        html = (
            _curl_box("STEP 1 — TOKEN", "#1e66f5", curl_token)
            + "<div style='height:12px'></div>"
            + _curl_box("STEP 2 — API CALL", "#40a02b", curl_api)
            + "<div style='height:12px'></div>"
            + _curl_box("ONE-LINER", "#8839ef", curl_oneliner)
        )
        return format_html(html)

    # ── Save / Delete ────────────────────────────────────────────────────

    def save_model(self, request, obj: ApiConsumer, form, change):
        if obj.auth_type == "api_key" and not obj.api_key:
            obj.api_key = secrets.token_urlsafe(32)
        elif obj.auth_type == "jwt":
            obj.api_key = None  # Evita violazione unique su stringa vuota

        super().save_model(request, obj, form, change)
        self._sync_consumer(request, obj)

    def delete_model(self, request, obj: ApiConsumer):
        self._delete_from_gateway(obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for consumer in queryset:
            self._delete_from_gateway(consumer)
        super().delete_queryset(request, queryset)

    # ── Actions ──────────────────────────────────────────────────────────

    @admin.action(description="Sincronizza con gateway (APISIX/Keycloak)")
    def sync_selected_to_gateway(self, request, queryset):
        for consumer in queryset:
            self._sync_consumer(request, consumer)

    @admin.action(description="Rigenera API key e sincronizza")
    def regenerate_api_keys(self, request, queryset):
        for consumer in queryset.filter(auth_type="api_key"):
            consumer.api_key = secrets.token_urlsafe(32)
            consumer.save(update_fields=["api_key"])
            self._sync_consumer(request, consumer)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _sync_consumer(self, request, consumer: ApiConsumer) -> None:
        """Sincronizza il consumer con il gateway appropriato."""
        try:
            if consumer.auth_type == "api_key":
                sync_consumer_to_apisix(consumer)
                ApiConsumer.objects.filter(pk=consumer.pk).update(
                    apisix_synced=True, sync_error="", last_synced_at=timezone.now(),
                )
                messages.success(request, f"'{consumer.username}' sincronizzato con APISIX.")
            else:
                sync_consumer_to_keycloak(consumer)
                ApiConsumer.objects.filter(pk=consumer.pk).update(
                    keycloak_synced=True, sync_error="", last_synced_at=timezone.now(),
                    keycloak_client_id=consumer.keycloak_client_id,
                    keycloak_client_secret=consumer.keycloak_client_secret,
                )
                messages.success(request, f"'{consumer.username}' sincronizzato con Keycloak.")
        except Exception as e:
            ApiConsumer.objects.filter(pk=consumer.pk).update(
                sync_error=str(e),
                **{"apisix_synced" if consumer.auth_type == "api_key" else "keycloak_synced": False},
            )
            messages.warning(request, f"Sync fallita per '{consumer.username}': {e}")

    def _delete_from_gateway(self, consumer: ApiConsumer) -> None:
        """Rimuove il consumer dal gateway (best effort)."""
        try:
            if consumer.auth_type == "api_key":
                delete_consumer_from_apisix(consumer.username)
            elif consumer.keycloak_client_id:
                delete_client_from_keycloak(consumer.keycloak_client_id)
        except Exception:
            logger.warning("Errore rimozione gateway per %s", consumer.username, exc_info=True)
