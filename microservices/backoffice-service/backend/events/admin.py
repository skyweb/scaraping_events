"""
Configurazione admin per gli eventi (Staging e Production).

Include: widget personalizzati, filtri, form, admin con tab Unfold,
admin per Celery TaskResult e API Request Log.
"""
import json
import logging
from datetime import timedelta

from django import forms
from django.contrib import admin
from django.db.models import Avg, Max, Min, Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin
from django_ckeditor_5.widgets import CKEditor5Widget
from django_celery_results.models import TaskResult
from django_celery_results.admin import TaskResultAdmin as BaseTaskResultAdmin
from rest_framework_tracking.models import APIRequestLog

from .models import ProductionEvent, StagingEvent
from .admin_mixins import EventDisplayMixin
from .admin_utils import format_datetime_italian, render_chip, render_json_preview
from comuni_istat.models import ComuneItaliano
from comuni_istat.admin import ProvinciaFilter, RegioneFilter
from scraping.admin import CategoryFilter

logger = logging.getLogger(__name__)


# =============================================================================
# Widget personalizzati per i campi del form
# =============================================================================

class CityAutocompleteWidget(forms.TextInput):
    """Campo testo con autocomplete che suggerisce i comuni italiani dal database."""
    template_name = 'admin/widgets/city_autocomplete.html'

    def get_context(self, name, value, attrs):
        """Aggiunge la lista dei comuni al contesto del template."""
        context = super().get_context(name, value, attrs)
        context['comuni'] = ComuneItaliano.objects.values_list('comune', flat=True)
        return context


class CategoryChipsWidget(forms.TextInput):
    """Campo che visualizza le categorie come chip editabili (tag separati da virgola)."""
    template_name = 'admin/widgets/category_chips.html'

    def format_value(self, value):
        """Converte la lista Python in stringa separata da virgole per il template."""
        if value is None:
            return ''
        if isinstance(value, list):
            return ','.join(value)
        return value

    def value_from_datadict(self, data, files, name):
        """Converte la stringa dal form in lista Python."""
        value = data.get(name, '')
        if value:
            return [v.strip() for v in value.split(',') if v.strip()]
        return []


# =============================================================================
# Widget condivisi tra StagingEventForm e ProductionEventForm
# =============================================================================

EVENT_FORM_WIDGETS = {
    'title': forms.TextInput(attrs={'style': 'width: 100%;'}),
    'description': CKEditor5Widget(config_name='default'),
    'city': CityAutocompleteWidget(),
    'city_name': CityAutocompleteWidget(),
    'category': CategoryChipsWidget(),
    'location_name': forms.TextInput(attrs={'style': 'width: 100%;'}),
    'location_address': forms.TextInput(attrs={'style': 'width: 100%;'}),
    'price': forms.TextInput(attrs={'style': 'width: 100%;'}),
    'image_url': forms.TextInput(attrs={'style': 'width: 100%;'}),
    'website': forms.URLInput(attrs={'style': 'width: 100%;'}),
}


# =============================================================================
# Filtro per stato temporale (Passato / In corso / Futuro)
# =============================================================================

class TemporalStatusFilter(admin.SimpleListFilter):
    """Filtro sidebar per stato temporale degli eventi (Passato, In corso, Futuro)."""
    title = 'Stato'
    parameter_name = 'stato'

    def lookups(self, request, model_admin):
        """Restituisce le opzioni del filtro."""
        return [
            ('passato', 'Passato'),
            ('in_corso', 'In corso'),
            ('futuro', 'Futuro'),
        ]

    def queryset(self, request, queryset):
        """Filtra il queryset in base allo stato temporale selezionato."""
        today = timezone.now().date()
        if self.value() == 'passato':
            return queryset.filter(date_start__isnull=False).extra(
                where=["COALESCE(date_end, date_start) < %s"], params=[today]
            )
        if self.value() == 'in_corso':
            return queryset.filter(
                date_start__lte=today,
            ).extra(
                where=["COALESCE(date_end, date_start) >= %s"], params=[today]
            )
        if self.value() == 'futuro':
            return queryset.filter(date_start__gt=today)
        return queryset


# =============================================================================
# Form per StagingEvent e ProductionEvent
# =============================================================================

class StagingEventForm(forms.ModelForm):
    """Form per StagingEvent con widget personalizzati (CKEditor, autocomplete città, chip categorie)."""
    class Meta:
        model = StagingEvent
        fields = '__all__'
        widgets = EVENT_FORM_WIDGETS
        labels = {
            'title': 'Titolo',
            'date_start': 'Data inizio',
            'date_end': 'Data fine',
            'city_name': 'Città',
            'location_name': 'Luogo',
            'location_address': 'Indirizzo',
            'category': 'Categoria',
            'description': 'Descrizione',
            'image_url': 'URL Immagine',
            'price': 'Prezzo',
            'url': 'URL Evento',
        }


class ProductionEventForm(forms.ModelForm):
    """Form per ProductionEvent con widget personalizzati (CKEditor, autocomplete città, chip categorie)."""
    class Meta:
        model = ProductionEvent
        fields = '__all__'
        widgets = EVENT_FORM_WIDGETS


# =============================================================================
# Admin per StagingEvent — interfaccia a tab con Unfold
# =============================================================================

@admin.register(StagingEvent)
class StagingEventAdmin(EventDisplayMixin, ModelAdmin):
    """Admin StagingEvent con layout a tab Unfold, chip stato, anteprima immagini e JSON colorato."""
    form = StagingEventForm

    class Media:
        css = {
            'all': ('events/css/admin_custom.css',)
        }
        js = ('events/js/tab_persist.js',)

    list_display = ['image_thumbnail', 'title', 'event_status_chip', 'category_list', 'city_name', 'source', 'created_at']
    list_display_links = ['title']
    list_filter = [TemporalStatusFilter, 'city_name', 'source', CategoryFilter]
    search_fields = ['title', 'description', 'uuid']
    readonly_fields = [
        'created_at', 'image_preview', 'image_thumbnail', 'description_preview',
        'json_preview', 'clickable_url', 'clickable_image_url', 'source', 'uuid',
        'content_hash', 'category_list', 'date_start_display',
        'event_status_chip', 'creation_date_display',
        'location_map_preview', 'schema_org_preview', 'raw_data_preview',
        'batch_file', 'scraped_at', 'ai_transform_button', 'ai_description_button',
    ]

    def get_search_results(self, request, queryset, search_term):
        """Ricerca con priorità: prima match nel titolo, poi nel contenuto."""
        if not search_term:
            return queryset, False

        from django.db.models import Case, When, Value, IntegerField, Q

        q_title = Q(title__icontains=search_term)
        q_desc = Q(description__icontains=search_term)
        q_uuid = Q(uuid__icontains=search_term)

        queryset = queryset.filter(q_title | q_desc | q_uuid).annotate(
            _search_rank=Case(
                When(q_title, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        ).order_by('_search_rank', '-created_at')

        return queryset, False

    actions = ['run_nlp_analysis']
    list_per_page = 50

    @admin.action(description="Analisi NLP (estrai entità da description)")
    def run_nlp_analysis(self, request, queryset):
        """Lancia analisi NLP sugli eventi selezionati via Celery."""
        from nlp.tasks import nlp_analyze_events

        uuids = list(queryset.values_list('uuid', flat=True))
        count = len(uuids)

        if count > 50:
            # Per molti eventi, lancia task Celery async
            source = queryset.values_list('source', flat=True).first()
            task = nlp_analyze_events.delay(source=source, limit=count)
            self.message_user(request, f"Analisi NLP avviata in background per {count} eventi (task: {task.id})")
        else:
            # Per pochi eventi, esegui sincrono
            try:
                from nlp.extractor import analyze_staging_event
                enriched = 0
                for event in queryset.filter(description__isnull=False).exclude(description=""):
                    entities = analyze_staging_event(event)
                    if entities:
                        raw = event.raw_data or {}
                        raw["nlp"] = entities
                        StagingEvent.objects.filter(pk=event.pk).update(raw_data=raw)
                        enriched += 1
                self.message_user(request, f"Analisi NLP completata: {enriched}/{count} eventi arricchiti")
            except Exception as e:
                self.message_user(request, f"Errore NLP: {e}", level='error')

    fieldsets = (
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">info</span> Informazioni Evento</span>'), {
            'fields': (
                ('source', 'uuid', 'creation_date_display'),
                ('date_start', 'date_end', 'event_status_chip'),
                'title',
                ('city_name', 'location_name', 'location_address'),
                'location_map_preview',
                'category_list',
                'clickable_url',
            ),
            'classes': ['tab'],
        }),
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">description</span> Contenuto</span>'), {
            'fields': (
                'ai_description_button',
                'description',
                'category',
                ('image_preview', 'clickable_image_url'),
                'price',
            ),
            'classes': ['tab'],
        }),
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">code</span> Dati Tecnici</span>'), {
            'fields': (
                ('content_hash', 'scraped_at', 'batch_file'),
                'ai_transform_button',
                'schema_org_preview',
                'raw_data_preview',
            ),
            'classes': ['tab'],
        }),
    )

    def creation_date_display(self, obj):
        """Data di creazione (created_at) formattata dd/mm/yyyy HH:MM."""
        return format_datetime_italian(obj.created_at)
    creation_date_display.short_description = "Data creazione"

    def location_map_preview(self, obj):
        """Mappa Leaflet read-only per le coordinate dell'evento."""
        if not obj.location_coordinates:
            return "-"
        lat = obj.location_coordinates.y
        lng = obj.location_coordinates.x
        map_id = f"map-staging-{obj.pk}"
        return mark_safe(
            f'<div id="{map_id}" style="height:300px;width:100%;border-radius:0.5rem;margin-top:0.5rem;"></div>'
            f'<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />'
            f'<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
            f'<script>'
            f'(function() {{'
            f'  function initMap() {{'
            f'    if (typeof L === "undefined") {{ setTimeout(initMap, 100); return; }}'
            f'    var map = L.map("{map_id}").setView([{lat}, {lng}], 15);'
            f'    L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{'
            f'      attribution: "&copy; OpenStreetMap"'
            f'    }}).addTo(map);'
            f'    L.marker([{lat}, {lng}]).addTo(map);'
            f'    setTimeout(function() {{ map.invalidateSize(); }}, 200);'
            f'  }}'
            f'  initMap();'
            f'}})();'
            f'</script>'
        )
    location_map_preview.short_description = "Mappa"

    def schema_org_preview(self, obj):
        """Renderizza il campo schema_org come JSON con sintassi colorata."""
        return render_json_preview(obj.schema_org, f"schema-org-{obj.pk}-staging")
    schema_org_preview.short_description = "Schema.org"

    def raw_data_preview(self, obj):
        """Renderizza il campo raw_data come JSON con sintassi colorata."""
        return render_json_preview(obj.raw_data, f"raw-data-{obj.pk}-staging")
    raw_data_preview.short_description = "Raw Data"

    def ai_transform_button(self, obj):
        """Pulsante per trasformare raw_data in schema_org tramite AI."""
        if not obj.raw_data:
            return mark_safe('<span style="color:#6b7280;font-size:0.85rem;">Nessun raw_data disponibile</span>')

        models_options = ''.join(
            f'<option value="{m}"{" selected" if m == "gemini-2.5-flash" else ""}>{m}</option>'
            for m in [
                "gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro",
                "llama-3.3-70b-versatile", "llama-3.1-8b-instant", "qwen/qwen3-32b",
            ]
        )
        return mark_safe(f'''
            <div style="display:flex;align-items:center;gap:0.75rem;flex-wrap:wrap;">
                <select id="ai-model-select" style="padding:0.4rem 0.6rem;border:1px solid #d1d5db;
                    border-radius:0.375rem;font-size:0.85rem;background:#fff;">
                    {models_options}
                </select>
                <button type="button" id="ai-transform-btn" onclick="aiTransform({obj.pk})"
                    style="padding:0.5rem 1.25rem;background:#7c3aed;color:#fff;border:none;
                    border-radius:0.375rem;cursor:pointer;font-size:0.85rem;font-weight:600;
                    display:inline-flex;align-items:center;gap:0.4rem;"
                    onmouseover="this.style.background='#6d28d9'"
                    onmouseout="this.style.background='#7c3aed'">
                    <span class="material-symbols-outlined" style="font-size:1.1rem;">auto_awesome</span>
                    Genera Schema.org
                </button>
                <span id="ai-transform-status" style="font-size:0.85rem;color:#6b7280;"></span>
            </div>
            <script>
            function aiTransform(eventId) {{
                var btn = document.getElementById("ai-transform-btn");
                var status = document.getElementById("ai-transform-status");
                var model = document.getElementById("ai-model-select").value;
                btn.disabled = true;
                btn.style.opacity = "0.6";
                btn.style.cursor = "wait";
                status.textContent = "Trasformazione in corso...";
                status.style.color = "#7c3aed";

                fetch("/admin/events/stagingevent/" + eventId + "/ai-transform/", {{
                    method: "POST",
                    headers: {{
                        "Content-Type": "application/json",
                        "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,
                    }},
                    body: JSON.stringify({{model: model}}),
                }})
                .then(function(r) {{ return r.json().then(function(d) {{ return {{ok: r.ok, data: d}}; }}); }})
                .then(function(res) {{
                    if (res.ok) {{
                        var msg = "Schema.org generato con " + res.data.model;
                        msg += formatQuota(res.data.quota);
                        status.innerHTML = msg;
                        status.style.color = "#16a34a";
                        setTimeout(function() {{ location.reload(); }}, 2500);
                    }} else {{
                        status.textContent = "Errore: " + (res.data.error || "sconosciuto");
                        status.style.color = "#dc2626";
                        btn.disabled = false;
                        btn.style.opacity = "1";
                        btn.style.cursor = "pointer";
                    }}
                }})
                .catch(function(e) {{
                    status.textContent = "Errore di rete: " + e.message;
                    status.style.color = "#dc2626";
                    btn.disabled = false;
                    btn.style.opacity = "1";
                    btn.style.cursor = "pointer";
                }});
            }}
            function formatQuota(q) {{
                if (!q) return "";
                if (q.provider === "groq" && q.remaining_requests != null) {{
                    return " — <span style='color:#6b7280;font-size:0.8rem;'>"
                        + "Residuo: " + q.remaining_requests + "/" + (q.limit_requests || "?") + " req"
                        + (q.remaining_tokens ? ", " + Number(q.remaining_tokens).toLocaleString() + " token" : "")
                        + (q.reset_requests ? " (reset " + q.reset_requests + ")" : "")
                        + "</span>";
                }}
                if (q.provider === "gemini" && q.remaining_requests != null) {{
                    return " — <span style='color:#6b7280;font-size:0.8rem;'>"
                        + "Residuo: " + q.remaining_requests + "/" + (q.limit_requests || "?") + " req/giorno"
                        + " (usate oggi: " + (q.used_today || 0) + ")"
                        + (q.rpm ? ", max " + q.rpm + " req/min" : "")
                        + "</span>";
                }}
                return "";
            }}
            </script>
        ''')
    ai_transform_button.short_description = "AI Transform"

    def ai_description_button(self, obj):
        """Pulsante per estrarre info strutturate dalla description in raw_data tramite AI."""
        raw = obj.raw_data or {}
        description = (raw.get('data') or {}).get('description', '') if isinstance(raw.get('data'), dict) else raw.get('description', '')
        if not description:
            return mark_safe('<span style="color:#6b7280;font-size:0.85rem;">Nessuna description in raw_data</span>')

        models_options = ''.join(
            f'<option value="{m}"{" selected" if m == "gemini-2.5-flash" else ""}>{m}</option>'
            for m in [
                "gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro",
                "llama-3.3-70b-versatile", "llama-3.1-8b-instant", "qwen/qwen3-32b",
            ]
        )
        return mark_safe(f'''
            <div style="display:flex;align-items:center;gap:0.75rem;flex-wrap:wrap;">
                <select id="ai-desc-model-select" style="padding:0.4rem 0.6rem;border:1px solid #d1d5db;
                    border-radius:0.375rem;font-size:0.85rem;background:#fff;">
                    {models_options}
                </select>
                <button type="button" id="ai-desc-btn" onclick="aiDescriptionTransform({obj.pk})"
                    style="padding:0.5rem 1.25rem;background:#0891b2;color:#fff;border:none;
                    border-radius:0.375rem;cursor:pointer;font-size:0.85rem;font-weight:600;
                    display:inline-flex;align-items:center;gap:0.4rem;"
                    onmouseover="this.style.background='#0e7490'"
                    onmouseout="this.style.background='#0891b2'">
                    <span class="material-symbols-outlined" style="font-size:1.1rem;">auto_awesome</span>
                    Estrai descrizione strutturata
                </button>
                <span id="ai-desc-status" style="font-size:0.85rem;color:#6b7280;"></span>
            </div>
            <script>
            function aiDescriptionTransform(eventId) {{
                var btn = document.getElementById("ai-desc-btn");
                var status = document.getElementById("ai-desc-status");
                var model = document.getElementById("ai-desc-model-select").value;
                btn.disabled = true;
                btn.style.opacity = "0.6";
                btn.style.cursor = "wait";
                status.textContent = "Estrazione in corso...";
                status.style.color = "#0891b2";

                fetch("/admin/events/stagingevent/" + eventId + "/ai-description/", {{
                    method: "POST",
                    headers: {{
                        "Content-Type": "application/json",
                        "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,
                    }},
                    body: JSON.stringify({{model: model}}),
                }})
                .then(function(r) {{ return r.json().then(function(d) {{ return {{ok: r.ok, data: d}}; }}); }})
                .then(function(res) {{
                    if (res.ok) {{
                        var msg = "Descrizione aggiornata con " + res.data.model;
                        msg += formatQuotaDesc(res.data.quota);
                        status.innerHTML = msg;
                        status.style.color = "#16a34a";
                        setTimeout(function() {{ location.reload(); }}, 2500);
                    }} else {{
                        status.textContent = "Errore: " + (res.data.error || "sconosciuto");
                        status.style.color = "#dc2626";
                        btn.disabled = false;
                        btn.style.opacity = "1";
                        btn.style.cursor = "pointer";
                    }}
                }})
                .catch(function(e) {{
                    status.textContent = "Errore di rete: " + e.message;
                    status.style.color = "#dc2626";
                    btn.disabled = false;
                    btn.style.opacity = "1";
                    btn.style.cursor = "pointer";
                }});
            }}
            function formatQuotaDesc(q) {{
                if (!q) return "";
                if (q.provider === "groq" && q.remaining_requests != null) {{
                    return " — <span style='color:#6b7280;font-size:0.8rem;'>"
                        + "Residuo: " + q.remaining_requests + "/" + (q.limit_requests || "?") + " req"
                        + (q.remaining_tokens ? ", " + Number(q.remaining_tokens).toLocaleString() + " token" : "")
                        + (q.reset_requests ? " (reset " + q.reset_requests + ")" : "")
                        + "</span>";
                }}
                if (q.provider === "gemini" && q.remaining_requests != null) {{
                    return " — <span style='color:#6b7280;font-size:0.8rem;'>"
                        + "Residuo: " + q.remaining_requests + "/" + (q.limit_requests || "?") + " req/giorno"
                        + " (usate oggi: " + (q.used_today || 0) + ")"
                        + (q.rpm ? ", max " + q.rpm + " req/min" : "")
                        + "</span>";
                }}
                return "";
            }}
            </script>
        ''')
    ai_description_button.short_description = "AI Descrizione"

    def get_urls(self):
        """Aggiunge URL custom per le trasformazioni AI."""
        from django.urls import path
        urls = super().get_urls()
        custom = [
            path(
                '<int:pk>/ai-transform/',
                self.admin_site.admin_view(self.ai_transform_view),
                name='stagingevent-ai-transform',
            ),
            path(
                '<int:pk>/ai-description/',
                self.admin_site.admin_view(self.ai_description_view),
                name='stagingevent-ai-description',
            ),
        ]
        return custom + urls

    def ai_transform_view(self, request, pk):
        """Endpoint admin per trasformare raw_data → schema_org via AI."""
        from django.http import JsonResponse
        from ai_transform.gemini import transform_event

        if request.method != 'POST':
            return JsonResponse({'error': 'Metodo non consentito'}, status=405)

        try:
            obj = StagingEvent.objects.get(pk=pk)
        except StagingEvent.DoesNotExist:
            return JsonResponse({'error': 'Evento non trovato'}, status=404)

        if not obj.raw_data:
            return JsonResponse({'error': 'Nessun raw_data disponibile'}, status=400)

        body = json.loads(request.body)
        model = body.get('model', 'gemini-2.5-flash')

        try:
            result, quota_info = transform_event(obj.raw_data, model, thinking=False)
            obj.schema_org = result
            obj.save(update_fields=['schema_org'])
            return JsonResponse({'ok': True, 'model': model, 'quota': quota_info})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    def ai_description_view(self, request, pk):
        """Endpoint admin per estrarre descrizione strutturata da raw_data.description via AI."""
        from django.http import JsonResponse
        from ai_transform.gemini import transform_text

        if request.method != 'POST':
            return JsonResponse({'error': 'Metodo non consentito'}, status=405)

        try:
            obj = StagingEvent.objects.get(pk=pk)
        except StagingEvent.DoesNotExist:
            return JsonResponse({'error': 'Evento non trovato'}, status=404)

        raw = obj.raw_data or {}
        description = (raw.get('data') or {}).get('description', '') if isinstance(raw.get('data'), dict) else raw.get('description', '')
        if not description:
            return JsonResponse({'error': 'Nessuna description in raw_data'}, status=400)

        body = json.loads(request.body)
        model = body.get('model', 'gemini-2.5-flash')

        prompt = (
            "Estraimi in modo strutturato le informazioni da questo testo di un evento. "
            "Restituisci SOLO un frammento HTML (NO tag html, head, body, doctype). "
            "Usa questi tag: <p> per paragrafi, <h3> per sezioni principali, <h4> per sottosezioni, "
            "<ul>/<li> per elenchi, <strong> per etichette/enfasi, <a href=\"...\"> per link e email (mailto:). "
            "Struttura il contenuto in sezioni logiche (es. Descrizione evento, Organizzatore, "
            "Dettagli, Orari, Contatti). Usa liste annidate <ul> dentro <li> per sotto-dettagli. "
            "Mantieni la lingua originale del testo. Non aggiungere informazioni non presenti nel testo."
        )

        try:
            result, quota_info = transform_text(prompt, description, model, thinking=False)
            obj.description = result
            obj.save(update_fields=['description'])
            return JsonResponse({'ok': True, 'model': model, 'quota': quota_info})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    def time_info_html(self, obj):
        """Visualizza time_info con rendering HTML."""
        if not obj.time_info:
            return "-"
        return mark_safe(obj.time_info)
    time_info_html.short_description = "Orario info"


# =============================================================================
# Admin per ProductionEvent — interfaccia a tab con Unfold
# =============================================================================

@admin.register(ProductionEvent)
class ProductionEventAdmin(EventDisplayMixin, ModelAdmin):
    """Admin ProductionEvent con layout a tab Unfold, chip stato, anteprima immagini e JSON colorato."""
    form = ProductionEventForm

    class Media:
        css = {
            'all': ('events/css/admin_custom.css',)
        }

    list_display = ['image_thumbnail', 'title', 'event_status_chip', 'category_list', 'city', 'source', 'date_start', 'is_active']
    list_display_links = ['title']
    list_filter = ['is_active', 'city', 'source', CategoryFilter]
    search_fields = ['title', 'description', 'uuid']
    readonly_fields = [
        'created_at', 'updated_at', 'image_preview', 'image_thumbnail', 'description_preview',
        'json_preview', 'clickable_url', 'clickable_image_url', 'source', 'uuid',
        'content_hash', 'category_list', 'date_start_display', 'date_start_ro', 'date_end_ro',
    ]
    list_per_page = 50

    fieldsets = (
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">info</span> Informazioni Evento</span>'), {
            'fields': (
                ('source', 'uuid', 'date_start_ro', 'date_end_ro'),
                'title',
                ('city', 'location_address'),
                'location_name',
                'clickable_url',
                'is_active',
            ),
            'classes': ['tab'],
        }),
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">description</span> Contenuto</span>'), {
            'fields': (
                'description',
                'category',
                ('image_preview', 'clickable_image_url'),
                ('price', 'website'),
            ),
            'classes': ['tab'],
        }),
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">calendar_month</span> Date e Orari</span>'), {
            'fields': (
                'date_start_display',
                ('date_start', 'date_end'),
                ('time_start', 'time_end'),
                ('time_info', 'schedule', 'weekdays'),
            ),
            'classes': ['tab'],
        }),
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">code</span> Dati Tecnici</span>'), {
            'fields': (
                'content_hash',
                ('scraped_at', 'created_at', 'updated_at'),
            ),
            'classes': ['tab'],
        }),
    )


# =============================================================================
# Admin per Celery Task Results — chip colorati per lo stato
# =============================================================================

STATUS_COLORS = {
    'SUCCESS': ('#065f46', '#d1fae5'),
    'FAILURE': ('#991b1b', '#fee2e2'),
    'PENDING': ('#92400e', '#fef3c7'),
    'STARTED': ('#92400e', '#fef3c7'),
    'RETRY':   ('#92400e', '#fef3c7'),
    'REVOKED': ('#991b1b', '#fee2e2'),
}

admin.site.unregister(TaskResult)


@admin.register(TaskResult)
class CustomTaskResultAdmin(BaseTaskResultAdmin, ModelAdmin):
    """Admin personalizzato per i risultati dei task Celery con chip colorati per stato."""
    list_display = ['task_id', 'task_name', 'status_chip', 'task_kwargs', 'date_done']

    def status_chip(self, obj):
        """Chip colorato per stato Celery: verde=SUCCESS, rosso=FAILURE, arancio=altri."""
        color, bg = STATUS_COLORS.get(obj.status, ('#92400e', '#fef3c7'))
        return render_chip(obj.status, color, bg)
    status_chip.short_description = "Status"


# =============================================================================
# Admin per API Request Log — statistiche e benchmark
# =============================================================================

HTTP_STATUS_COLORS = {
    2: ('#065f46', '#d1fae5'),   # 2xx
    3: ('#1e40af', '#dbeafe'),   # 3xx
    4: ('#92400e', '#fef3c7'),   # 4xx
    5: ('#991b1b', '#fee2e2'),   # 5xx
}

HTTP_METHOD_COLORS = {
    'GET': ('#1e40af', '#dbeafe'),
    'POST': ('#065f46', '#d1fae5'),
    'PUT': ('#92400e', '#fef3c7'),
    'PATCH': ('#92400e', '#fef3c7'),
    'DELETE': ('#991b1b', '#fee2e2'),
}

admin.site.unregister(APIRequestLog)


@admin.register(APIRequestLog)
class CustomAPIRequestLogAdmin(ModelAdmin):
    """Admin API Request Log — solo statistiche e benchmark, senza dettagli query/response."""
    list_display = [
        'request_date_display', 'method_chip', 'path', 'status_chip', 'response_time_chip',
        'username_persistent', 'remote_addr',
    ]
    list_filter = ['method', 'status_code', 'view_method', 'username_persistent']
    search_fields = ['path', 'username_persistent', 'remote_addr']
    date_hierarchy = 'requested_at'
    ordering = ['-requested_at']
    list_per_page = 50

    readonly_fields = [
        'requested_at', 'method', 'path', 'view', 'view_method',
        'status_code', 'response_ms', 'username_persistent',
        'remote_addr', 'host',
    ]
    fields = readonly_fields
    list_select_related = True

    def has_add_permission(self, request):
        """Impedisce la creazione manuale di log."""
        return False

    def has_change_permission(self, request, obj=None):
        """Log in sola lettura — nessuna modifica permessa."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Log in sola lettura — nessuna eliminazione permessa."""
        return False

    def request_date_display(self, obj):
        """Data della richiesta formattata dd/mm/yyyy HH:MM."""
        return format_datetime_italian(obj.requested_at)
    request_date_display.short_description = "Data"
    request_date_display.admin_order_field = 'requested_at'

    def status_chip(self, obj):
        """Chip colorato per HTTP status code (2xx verde, 4xx arancio, 5xx rosso)."""
        category = obj.status_code // 100 if obj.status_code else 0
        color, bg = HTTP_STATUS_COLORS.get(category, ('#6b7280', '#f3f4f6'))
        return render_chip(obj.status_code, color, bg)
    status_chip.short_description = "Status"

    def method_chip(self, obj):
        """Chip colorato per metodo HTTP (GET blu, POST verde, DELETE rosso)."""
        color, bg = HTTP_METHOD_COLORS.get(obj.method, ('#6b7280', '#f3f4f6'))
        return render_chip(obj.method, color, bg)
    method_chip.short_description = "Metodo"

    def response_time_chip(self, obj):
        """Chip colorato per tempo di risposta: verde <200ms, arancio <1000ms, rosso >1000ms."""
        ms = obj.response_ms
        if ms is None:
            return "-"
        if ms < 200:
            color, bg = '#065f46', '#d1fae5'
        elif ms < 1000:
            color, bg = '#92400e', '#fef3c7'
        else:
            color, bg = '#991b1b', '#fee2e2'
        return render_chip(f'{ms} ms', color, bg)
    response_time_chip.short_description = "Tempo"

    def changelist_view(self, request, extra_context=None):
        """Aggiunge statistiche aggregate e dati per il grafico nella vista lista."""
        qs = self.get_queryset(request)
        from django.contrib.admin.views.main import ChangeList
        try:
            cl = ChangeList(
                request, self.model, self.list_display, self.list_display_links,
                self.list_filter, self.date_hierarchy, self.search_fields,
                self.list_select_related, self.list_per_page, self.list_max_show_all,
                self.list_editable, self, self.sortable_by, self.search_help_text,
            )
            qs = cl.get_queryset(request)
        except Exception:
            logger.warning("Impossibile costruire ChangeList per le statistiche API", exc_info=True)

        stats = qs.aggregate(
            total=Count('id'),
            avg_ms=Avg('response_ms'),
            max_ms=Max('response_ms'),
            min_ms=Min('response_ms'),
        )

        # Dati grafico: richieste per giorno (ultimi 30 giorni)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        daily_data = (
            qs.filter(requested_at__gte=thirty_days_ago)
            .annotate(date=TruncDate('requested_at'))
            .values('date')
            .annotate(count=Count('id'), avg_time=Avg('response_ms'))
            .order_by('date')
        )

        chart_labels = [d['date'].strftime('%d/%m') for d in daily_data]
        chart_counts = [d['count'] for d in daily_data]
        chart_avg_ms = [round(d['avg_time'] or 0) for d in daily_data]

        chart_data = json.dumps({
            'labels': chart_labels,
            'datasets': [
                {
                    'label': 'Richieste',
                    'type': 'bar',
                    'data': chart_counts,
                    'backgroundColor': 'rgba(147, 51, 234, 0.5)',
                    'borderColor': 'rgb(147, 51, 234)',
                    'borderWidth': 1,
                    'yAxisID': 'y',
                },
                {
                    'label': 'Tempo medio (ms)',
                    'type': 'line',
                    'data': chart_avg_ms,
                    'borderColor': 'rgb(234, 88, 12)',
                    'backgroundColor': 'rgba(234, 88, 12, 0.1)',
                    'borderWidth': 2,
                    'tension': 0.3,
                    'fill': True,
                    'yAxisID': 'y1',
                },
            ],
        })

        extra_context = extra_context or {}
        extra_context['api_stats'] = stats
        extra_context['chart_data'] = chart_data
        extra_context['api_stats_html'] = format_html(
            '<div style="display:flex;gap:1.5rem;flex-wrap:wrap;padding:1rem;margin-bottom:1rem;'
            'background:#f9fafb;border:1px solid #e5e7eb;border-radius:0.5rem;">'
            '<div><span style="font-size:0.75rem;color:#6b7280;">Richieste</span>'
            '<div style="font-size:1.25rem;font-weight:700;color:#111827;">{}</div></div>'
            '<div><span style="font-size:0.75rem;color:#6b7280;">Tempo medio</span>'
            '<div style="font-size:1.25rem;font-weight:700;color:#111827;">{} ms</div></div>'
            '<div><span style="font-size:0.75rem;color:#6b7280;">Tempo min</span>'
            '<div style="font-size:1.25rem;font-weight:700;color:#065f46;">{} ms</div></div>'
            '<div><span style="font-size:0.75rem;color:#6b7280;">Tempo max</span>'
            '<div style="font-size:1.25rem;font-weight:700;color:#991b1b;">{} ms</div></div>'
            '</div>',
            stats['total'],
            round(stats['avg_ms'] or 0),
            stats['min_ms'] or 0,
            stats['max_ms'] or 0,
        )
        return super().changelist_view(request, extra_context=extra_context)
