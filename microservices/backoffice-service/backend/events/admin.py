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
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin
from django_ckeditor_5.widgets import CKEditor5Widget
from django_celery_results.models import TaskResult
from django_celery_results.admin import TaskResultAdmin as BaseTaskResultAdmin
from rest_framework_tracking.models import APIRequestLog

from .models import Event
from .admin_mixins import EventDisplayMixin
from .admin_utils import format_datetime_italian, render_chip, render_json_preview
from comuni_istat.models import Comune
from comuni_istat.admin import ProvinciaFilter, RegioneFilter
from scraping.admin import CategoryFilter

logger = logging.getLogger(__name__)

# Modelli AI disponibili per i pulsanti di trasformazione admin
AI_AVAILABLE_MODELS = [
    "gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro",
    "llama-3.3-70b-versatile", "llama-3.1-8b-instant", "qwen/qwen3-32b",
]
AI_DEFAULT_MODEL = "gemini-2.5-flash"


# =============================================================================
# Widget personalizzati per i campi del form
# =============================================================================

class CityAutocompleteWidget(forms.TextInput):
    """Campo testo con autocomplete che suggerisce i comuni italiani dal database."""
    template_name = 'admin/widgets/city_autocomplete.html'

    def get_context(self, name, value, attrs):
        """Aggiunge la lista dei comuni al contesto del template."""
        context = super().get_context(name, value, attrs)
        context['comuni'] = Comune.objects.values_list('comune', flat=True)
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
# Widget condivisi per EventForm
# =============================================================================

EVENT_FORM_WIDGETS = {
    'title': forms.TextInput(attrs={'style': 'width: 100%;'}),
    'description': CKEditor5Widget(config_name='default'),
    'city': CityAutocompleteWidget(),
    'category': CategoryChipsWidget(),
    'location_name': forms.TextInput(attrs={'style': 'width: 100%;'}),
    'location_address': forms.TextInput(attrs={'style': 'width: 100%;'}),
    'price': forms.TextInput(attrs={'style': 'width: 100%;'}),
    'image_url': forms.TextInput(attrs={'style': 'width: 100%;'}),
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
        if not self.value():
            return queryset
        today = timezone.now().date()
        qs = queryset.annotate(
            _effective_end=Coalesce('date_end', 'date_start'),
        )
        if self.value() == 'passato':
            return qs.filter(date_start__isnull=False, _effective_end__lt=today)
        if self.value() == 'in_corso':
            return qs.filter(date_start__lte=today, _effective_end__gte=today)
        if self.value() == 'futuro':
            return qs.filter(date_start__gt=today)
        return queryset


# =============================================================================
# Form per Event e Event
# =============================================================================

class EventForm(forms.ModelForm):
    """Form per Event con widget personalizzati (CKEditor, autocomplete città, chip categorie)."""
    class Meta:
        model = Event
        fields = '__all__'
        widgets = EVENT_FORM_WIDGETS
        labels = {
            'title': 'Titolo',
            'date_start': 'Data inizio',
            'date_end': 'Data fine',
            'city': 'Città',
            'location_name': 'Luogo',
            'location_address': 'Indirizzo',
            'category': 'Categoria',
            'description': 'Descrizione',
            'image_url': 'URL Immagine',
            'price': 'Prezzo',
            'url': 'URL Evento',
        }


# =============================================================================
# Admin per Event — interfaccia a tab con Unfold
# =============================================================================

@admin.register(Event)
class EventAdmin(EventDisplayMixin, ModelAdmin):
    """Admin Event con layout a tab Unfold, chip stato, anteprima immagini e JSON colorato."""
    form = EventForm

    class Media:
        css = {
            'all': ('events/css/admin_custom.css',)
        }
        js = ('events/js/tab_persist.js', 'events/js/row_inactive.js', 'events/js/location_map.js')

    list_display = ['image_thumbnail', 'title', 'event_status_chip', 'status_chip', 'category_list', 'city', 'source', 'is_active_chip', 'created_at']
    list_display_links = ['title']
    list_filter = ['status', TemporalStatusFilter, 'city', 'source', 'is_active', CategoryFilter]
    search_fields = ['title', 'description', 'uuid']
    readonly_fields = [
        'created_at', 'image_preview', 'image_thumbnail', 'description_preview',
        'json_preview', 'clickable_url', 'clickable_image_url', 'source', 'uuid',
        'content_hash', 'category_list', 'date_start_display',
        'event_status_chip', 'creation_date_display',
        'location_map_preview', 'schema_org_preview', 'raw_data_preview',
        'batch_file', 'scraped_at', 'ai_transform_button', 'ai_description_button',
        'rank_score',
    ]

    def get_search_results(self, request, queryset, search_term):
        """Ricerca pesata: title(A) > city(B) > location_name(C) > description(D)."""
        if not search_term:
            return queryset, False

        from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

        vector = (
            SearchVector('title', weight='A', config='italian')
            + SearchVector('city', weight='B', config='italian')
            + SearchVector('location_name', weight='C', config='italian')
            + SearchVector('description', weight='D', config='italian')
        )
        query = SearchQuery(search_term, config='italian')

        queryset = (
            queryset
            .annotate(rank=SearchRank(vector, query, weights=[0.1, 0.2, 0.4, 1.0]))
            .filter(rank__gt=0)
            .order_by('-rank')
        )

        return queryset, False

    @admin.display(description='Status', ordering='status')
    def status_chip(self, obj):
        """Chip verde per Pubblicato, arancio per Staging."""
        if obj.status == Event.Status.PUBLISHED:
            return format_html(
                '<span style="display:inline-block;padding:2px 10px;border-radius:9999px;'
                'font-size:.75rem;font-weight:600;color:#065f46;background:#d1fae5;">Pubblicato</span>'
            )
        return format_html(
            '<span style="display:inline-block;padding:2px 10px;border-radius:9999px;'
            'font-size:.75rem;font-weight:600;color:#92400e;background:#fef3c7;">Staging</span>'
        )

    @admin.display(description='Attivo', boolean=False, ordering='is_active')
    def is_active_chip(self, obj):
        """Chip verde/rosso per stato attivo."""
        if obj.is_active:
            return format_html(
                '<span style="display:inline-block;padding:2px 10px;border-radius:9999px;'
                'font-size:.75rem;font-weight:600;color:#065f46;background:#d1fae5;">Attivo</span>'
            )
        return format_html(
            '<span style="display:inline-block;padding:2px 10px;border-radius:9999px;'
            'font-size:.75rem;font-weight:600;color:#991b1b;background:#fee2e2;">Inattivo</span>'
        )

    actions = ['run_nlp_analysis']
    list_per_page = 50

    def save_model(self, request, obj, form, change):
        """Popola created_by/updated_by con lo username dell'utente admin."""
        username = request.user.get_username()
        if change:
            obj.updated_by = username
        else:
            obj.created_by = username
        super().save_model(request, obj, form, change)

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
                to_update: list[Event] = []
                for event in queryset.filter(description__isnull=False).exclude(description=""):
                    entities = analyze_staging_event(event)
                    if entities:
                        raw = event.raw_data or {}
                        raw["nlp"] = entities
                        event.raw_data = raw
                        to_update.append(event)
                if to_update:
                    Event.objects.bulk_update(to_update, ['raw_data'], batch_size=100)
                self.message_user(request, f"Analisi NLP completata: {len(to_update)}/{count} eventi arricchiti")
            except Exception as e:
                self.message_user(request, f"Errore NLP: {e}", level='error')

    fieldsets = (
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">info</span> Informazioni Evento</span>'), {
            'fields': (
                ('source', 'uuid', 'creation_date_display'),
                ('date_start', 'date_end', 'event_status_chip'),
                ('status', 'is_active', 'boost', 'rank_score'),
                'title',
                ('city', 'location_name', 'location_address'),
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
        location_name = (obj.location_name or "").replace('"', "&quot;")
        return mark_safe(
            f'<div id="map-event-location"'
            f' style="height:70vh;width:100%;border-radius:8px;margin-top:8px;"'
            f' data-lat="{lat}"'
            f' data-lng="{lng}"'
            f' data-location-name="{location_name}"></div>'
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

        from django.template.loader import render_to_string
        html = render_to_string('admin/events/ai_transform_button.html', {
            'pk': obj.pk,
            'models': AI_AVAILABLE_MODELS,
            'default_model': AI_DEFAULT_MODEL,
        })
        return mark_safe(html)
    ai_transform_button.short_description = "AI Transform"

    def ai_description_button(self, obj):
        """Pulsante per estrarre info strutturate dalla description in raw_data tramite AI."""
        raw = obj.raw_data or {}
        description = (raw.get('data') or {}).get('description', '') if isinstance(raw.get('data'), dict) else raw.get('description', '')
        if not description:
            return mark_safe('<span style="color:#6b7280;font-size:0.85rem;">Nessuna description in raw_data</span>')

        from django.template.loader import render_to_string
        html = render_to_string('admin/events/ai_description_button.html', {
            'pk': obj.pk,
            'models': AI_AVAILABLE_MODELS,
            'default_model': AI_DEFAULT_MODEL,
        })
        return mark_safe(html)
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
            obj = Event.objects.get(pk=pk)
        except Event.DoesNotExist:
            return JsonResponse({'error': 'Evento non trovato'}, status=404)

        if not obj.raw_data:
            return JsonResponse({'error': 'Nessun raw_data disponibile'}, status=400)

        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'error': 'JSON non valido'}, status=400)
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
            obj = Event.objects.get(pk=pk)
        except Event.DoesNotExist:
            return JsonResponse({'error': 'Evento non trovato'}, status=404)

        raw = obj.raw_data or {}
        description = (raw.get('data') or {}).get('description', '') if isinstance(raw.get('data'), dict) else raw.get('description', '')
        if not description:
            return JsonResponse({'error': 'Nessuna description in raw_data'}, status=400)

        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'error': 'JSON non valido'}, status=400)
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
