import logging
import os
import secrets

from django.contrib import admin, messages

logger = logging.getLogger(__name__)
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin

from .models import API_ACTIONS, API_RESOURCES, ApiConsumer
from .services import (
    delete_client_from_keycloak,
    delete_consumer_from_apisix,
    sync_consumer_to_apisix,
    sync_consumer_to_keycloak,
)

DOMAIN = os.environ.get("DOMAIN", "127.0.0.1.nip.io")
API_BASE = f"https://webservice.{DOMAIN}/api/v1/events/staging/"
TOKEN_URL = f"https://webservice.{DOMAIN}/auth/token"

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


_CHIP_STYLE = (
    "display:inline-block; padding:3px 10px; border-radius:12px; font-size:11px;"
    " font-weight:600; letter-spacing:0.3px;"
)


def _chip(label: str, active: bool) -> str:
    """Genera un chip colorato verde (attivo) o rosso (disattivo)."""
    bg = "#40a02b" if active else "#e64553"
    return f'<span style="{_CHIP_STYLE} background:{bg}; color:#fff;">{label}</span>'


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
        "username", "plan", "auth_type", "show_active_chip",
        "show_expiry_status", "show_sync_chip", "show_requests_today", "created_at",
    ]
    list_filter = ["plan", "auth_type", "is_active", "apisix_synced", "keycloak_synced"]
    search_fields = ["username", "contact_email", "description"]
    actions = ["sync_selected_to_gateway", "regenerate_api_keys"]

    fieldsets = [
        ("Configurazione", {
            "classes": ["tab"],
            "fields": [
                "username", "django_user", "plan", "auth_type", "is_active",
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
        ("Permessi API", {
            "classes": ["tab"],
            "description": "Matrice permessi per risorsa e azione.",
            "fields": ["show_permissions_matrix"],
        }),
        ("Stato sincronizzazione", {
            "classes": ["tab"],
            "fields": [
                "show_apisix_chip", "show_keycloak_chip", "sync_error", "last_synced_at",
            ],
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
        """Restituisce i campi di sola lettura, aggiungendo username e credenziali in modifica."""
        base = [
            "sync_error", "last_synced_at",
            "show_usage_today", "show_usage_month", "show_last_request",
            "show_curl_example", "show_permissions_matrix",
            "show_active_chip", "show_sync_chip",
            "show_apisix_chip", "show_keycloak_chip",
        ]
        if obj:
            return [*base, "username", "api_key", "keycloak_client_id", "keycloak_client_secret"]
        return [*base, "api_key", "keycloak_client_secret"]

    # ── Display methods ──────────────────────────────────────────────────

    @admin.display(description="Stato")
    def show_active_chip(self, obj: ApiConsumer) -> str:
        """Mostra un chip colorato verde/rosso per lo stato attivo/disattivo del consumer."""
        if obj.is_active:
            return mark_safe(_chip("Attivo", True))
        return mark_safe(_chip("Disattivo", False))

    @admin.display(description="Sync")
    def show_sync_chip(self, obj: ApiConsumer) -> str:
        """Mostra un chip colorato per lo stato di sincronizzazione con il gateway."""
        synced = obj.apisix_synced if obj.auth_type == "api_key" else obj.keycloak_synced
        if synced:
            return mark_safe(_chip("Sincronizzato", True))
        return mark_safe(_chip("Non sincronizzato", False))

    @admin.display(description="APISIX synced")
    def show_apisix_chip(self, obj: ApiConsumer) -> str:
        """Mostra un chip colorato per lo stato di sincronizzazione con APISIX."""
        if obj.apisix_synced:
            return mark_safe(_chip("Sincronizzato", True))
        return mark_safe(_chip("Non sincronizzato", False))

    @admin.display(description="Keycloak synced")
    def show_keycloak_chip(self, obj: ApiConsumer) -> str:
        """Mostra un chip colorato per lo stato di sincronizzazione con Keycloak."""
        if obj.keycloak_synced:
            return mark_safe(_chip("Sincronizzato", True))
        return mark_safe(_chip("Non sincronizzato", False))

    @admin.display(description="Scadenza")
    def show_expiry_status(self, obj: ApiConsumer) -> str:
        """Mostra la data di scadenza del consumer o 'Mai' se illimitato."""
        if obj.expires_at is None:
            return "Mai"
        if obj.is_expired:
            return format_html(
                '<span style="color:#e64553; font-weight:600">Scaduto ({})</span>',
                obj.expires_at.strftime("%d/%m/%Y"),
            )
        return obj.expires_at.strftime("%d/%m/%Y %H:%M")

    @admin.display(description="Req oggi")
    def show_requests_today(self, obj: ApiConsumer) -> str:
        """Mostra il numero di richieste odierne con eventuale limite giornaliero."""
        count = obj.get_requests_today()
        limit = obj.get_daily_limit()
        if limit:
            return f"{count} / {limit}"
        return str(count)

    @admin.display(description="Utilizzo oggi")
    def show_usage_today(self, obj: ApiConsumer) -> str:
        """Mostra il dettaglio dell'utilizzo giornaliero con percentuale rispetto al limite."""
        count = obj.get_requests_today()
        limit = obj.get_daily_limit()
        if limit:
            pct = min(100, round(count / limit * 100, 1))
            return f"{count} / {limit} richieste ({pct}%)"
        return f"{count} richieste (illimitate)"

    @admin.display(description="Utilizzo mese")
    def show_usage_month(self, obj: ApiConsumer) -> str:
        """Mostra il numero totale di richieste API nel mese corrente."""
        return f"{obj.get_requests_this_month()} richieste"

    @admin.display(description="Ultima richiesta")
    def show_last_request(self, obj: ApiConsumer) -> str:
        """Mostra data e ora dell'ultima richiesta API ricevuta dal consumer."""
        last = obj.get_last_request_at()
        if last:
            return last.strftime("%d/%m/%Y %H:%M:%S")
        return "Nessuna richiesta"

    @admin.display(description="Permessi API")
    def show_permissions_matrix(self, obj: ApiConsumer) -> str:
        """Mostra la matrice permessi risorse/azioni con checkbox interattive."""
        if not obj.pk:
            return "Salva il consumer per configurare i permessi."

        perms = obj.api_permissions or {}
        # Stili tabella
        th_style = (
            "padding:8px 12px; text-align:center; font-weight:600; font-size:12px;"
            " text-transform:uppercase; letter-spacing:0.5px;"
            " border-bottom:2px solid #45475a; color:#cdd6f4;"
        )
        td_style = "padding:6px 12px; text-align:center; border-bottom:1px solid #313244;"
        res_style = (
            "padding:8px 12px; font-weight:600; text-transform:capitalize;"
            " border-bottom:1px solid #313244; color:#cdd6f4;"
        )
        table_style = (
            "border-collapse:collapse; background:#1e1e2e; border-radius:8px;"
            " overflow:hidden; border:1px solid #45475a; margin:8px 0;"
        )

        # Intestazione
        headers = f"<th style='{th_style}'>Risorsa</th>"
        for action in API_ACTIONS:
            headers += f"<th style='{th_style}'>{action}</th>"

        # Righe
        rows = ""
        for resource in API_RESOURCES:
            resource_actions = perms.get(resource, [])
            row = f"<td style='{res_style}'>{resource}</td>"
            for action in API_ACTIONS:
                checked = "checked" if action in resource_actions else ""
                cb_name = f"perm_{resource}_{action}"
                row += (
                    f"<td style='{td_style}'>"
                    f"<input type='checkbox' name='{cb_name}' {checked}"
                    f" style='width:18px; height:18px; cursor:pointer;'>"
                    f"</td>"
                )
            rows += f"<tr>{row}</tr>"

        html = f"<table style='{table_style}'><tr>{headers}</tr>{rows}</table>"
        return mark_safe(html)

    @admin.display(description="Esempio chiamata cURL")
    def show_curl_example(self, obj: ApiConsumer) -> str:
        """Mostra un esempio cURL syntax-highlighted per testare le API con le credenziali del consumer."""
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
        client_secret = obj.keycloak_client_secret or "&lt;in attesa di sync Keycloak&gt;"

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

        # Pulsante "Invia richiesta" + area risposta per STEP 1
        btn_id = f"btn-token-{obj.pk}"
        resp_id = f"resp-token-{obj.pk}"
        client_secret_val = obj.keycloak_client_secret or ""
        body_param = f"grant_type=client_credentials&client_id={client_id}&client_secret={client_secret_val}"

        test_btn = mark_safe(
            f'<button type="button" id="{btn_id}" style="'
            f"margin-top:8px; padding:8px 18px; border:none; border-radius:6px;"
            f" background:#1e66f5; color:#fff; font-weight:600; font-size:13px;"
            f' cursor:pointer; font-family:inherit;"'
            f">▶ Invia richiesta</button>"
            f'<div id="{resp_id}" style="'
            f"display:none; margin-top:8px; background:#1e1e2e;"
            f" padding:14px 18px; border-radius:8px; font-family:'JetBrains Mono',monospace;"
            f" font-size:12px; line-height:1.6; white-space:pre-wrap; word-break:break-all;"
            f' border:1px solid #45475a; max-height:300px; overflow:auto;"'
            f"></div>"
            f"<script>"
            f"function colorizeJson(obj, indent) {{"
            f"  indent = indent || 0;"
            f"  var pad = '  '.repeat(indent);"
            f"  var pad1 = '  '.repeat(indent + 1);"
            f"  if (obj === null) return '<span style=\"color:#fab387\">null</span>';"
            f"  if (typeof obj === 'boolean') return '<span style=\"color:#fab387\">' + obj + '</span>';"
            f"  if (typeof obj === 'number') return '<span style=\"color:#fab387\">' + obj + '</span>';"
            f"  if (typeof obj === 'string') {{"
            f"    var s = obj.length > 80 ? obj.substring(0, 77) + '...' : obj;"
            f"    s = s.replace(/</g, '&lt;').replace(/>/g, '&gt;');"
            f"    return '<span style=\"color:{_STRING_COLOR}\">\"' + s + '\"</span>';"
            f"  }}"
            f"  if (Array.isArray(obj)) {{"
            f"    if (obj.length === 0) return '[]';"
            f"    var items = obj.map(function(v) {{ return pad1 + colorizeJson(v, indent + 1); }});"
            f"    return '[\\n' + items.join(',\\n') + '\\n' + pad + ']';"
            f"  }}"
            f"  var keys = Object.keys(obj);"
            f"  if (keys.length === 0) return '{{}}';"
            f"  var entries = keys.map(function(k) {{"
            f"    return pad1 + '<span style=\"color:{_FLAG_COLOR}\">\"' + k + '\"</span>: ' + colorizeJson(obj[k], indent + 1);"
            f"  }});"
            f"  return '{{\\n' + entries.join(',\\n') + '\\n' + pad + '}}';"
            f"}}"
            f'document.getElementById("{btn_id}").addEventListener("click", function() {{'
            f'  var btn = this;'
            f'  var resp = document.getElementById("{resp_id}");'
            f'  btn.disabled = true; btn.textContent = "⏳ Invio...";'
            f'  resp.style.display = "block";'
            f'  resp.innerHTML = "<span style=\\"color:#cdd6f4\\">Richiesta in corso...</span>";'
            f'  fetch("{TOKEN_URL}", {{'
            f'    method: "POST",'
            f'    headers: {{"Content-Type": "application/x-www-form-urlencoded"}},'
            f'    body: "{body_param}"'
            f"  }})"
            f"  .then(function(r) {{ return r.json(); }})"
            f"  .then(function(data) {{"
            f"    resp.innerHTML = colorizeJson(data);"
            f'    btn.textContent = "▶ Invia richiesta"; btn.disabled = false;'
            f"  }})"
            f"  .catch(function(err) {{"
            f'    resp.innerHTML = "<span style=\\"color:#e64553\\">Errore: " + err.message + "</span>";'
            f'    btn.textContent = "▶ Invia richiesta"; btn.disabled = false;'
            f"  }});"
            f"}});"
            f"</script>"
        )

        html = (
            _curl_box("STEP 1 — TOKEN", "#1e66f5", curl_token)
            + str(test_btn)
            + "<div style='height:12px'></div>"
            + _curl_box("STEP 2 — API CALL", "#40a02b", curl_api)
        )
        return mark_safe(html)

    # ── Save / Delete ────────────────────────────────────────────────────

    def save_model(self, request, obj: ApiConsumer, form, change):
        """Salva il consumer, genera API key se mancante e sincronizza con il gateway."""
        if obj.auth_type == "api_key" and not obj.api_key:
            obj.api_key = secrets.token_urlsafe(32)
        elif obj.auth_type == "jwt":
            obj.api_key = None  # Evita violazione unique su stringa vuota

        # Leggi matrice permessi dai checkbox del POST
        api_permissions: dict[str, list[str]] = {}
        for resource in API_RESOURCES:
            actions = []
            for action in API_ACTIONS:
                if request.POST.get(f"perm_{resource}_{action}"):
                    actions.append(action)
            api_permissions[resource] = actions
        obj.api_permissions = api_permissions

        super().save_model(request, obj, form, change)
        self._sync_consumer(request, obj)

    def delete_model(self, request, obj: ApiConsumer):
        """Elimina il consumer rimuovendolo prima dal gateway."""
        self._delete_from_gateway(obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """Elimina in blocco i consumer selezionati, rimuovendoli prima dal gateway."""
        for consumer in queryset:
            self._delete_from_gateway(consumer)
        super().delete_queryset(request, queryset)

    # ── Actions ──────────────────────────────────────────────────────────

    @admin.action(description="Sincronizza con gateway (APISIX/Keycloak)")
    def sync_selected_to_gateway(self, request, queryset):
        """Azione admin: sincronizza i consumer selezionati con APISIX o Keycloak."""
        for consumer in queryset:
            self._sync_consumer(request, consumer)

    @admin.action(description="Rigenera API key e sincronizza")
    def regenerate_api_keys(self, request, queryset):
        """Azione admin: rigenera le API key dei consumer selezionati e risincronizza con APISIX."""
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
