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
from .admin_utils import format_datetime_italian, render_chip
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
    'raw_data': forms.Textarea(attrs={'rows': 15, 'style': 'font-family: monospace; width: 100%;'}),
    'info_extra': forms.Textarea(attrs={'rows': 8, 'style': 'font-family: monospace; width: 100%;'}),
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

    list_display = ['image_thumbnail', 'title', 'event_status_chip', 'category_list', 'city_name', 'source', 'created_at']
    list_display_links = ['title']
    list_filter = [TemporalStatusFilter, 'city_name', 'source', CategoryFilter]
    search_fields = ['title', 'description', 'uuid']
    readonly_fields = [
        'created_at', 'image_preview', 'image_thumbnail', 'description_preview',
        'json_preview', 'clickable_url', 'clickable_image_url', 'source', 'uuid',
        'content_hash', 'category_list', 'date_start_display', 'date_start_ro', 'date_end_ro',
        'event_status_chip', 'creation_date_display', 'info_extra_details', 'time_info_html',
    ]
    list_per_page = 50

    fieldsets = (
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">info</span> Informazioni Evento</span>'), {
            'fields': (
                ('source', 'uuid', 'creation_date_display'),
                ('date_start_ro', 'date_end_ro', 'event_status_chip'),
                'title',
                'section',
                ('city_name', 'location_name', 'location_address'),
                'location_coordinates',
                'category_list',
                'clickable_url',
            ),
            'classes': ['tab'],
        }),
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">description</span> Contenuto</span>'), {
            'fields': (
                'description',
                'category',
                ('image_preview', 'clickable_image_url'),
                'price',
                'info_extra',
                'info_extra_details',
            ),
            'classes': ['tab'],
        }),
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">calendar_month</span> Date e Orari</span>'), {
            'fields': (
                'date_start_display',
                ('date_start', 'date_end'),
                ('time_start', 'time_end'),
                'time_info_html',
            ),
            'classes': ['tab'],
        }),
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">code</span> Dati Tecnici</span>'), {
            'fields': (
                'content_hash',
                'json_preview',
                'scraped_at',
            ),
            'classes': ['tab'],
        }),
    )

    def creation_date_display(self, obj):
        """Data di creazione (created_at) formattata dd/mm/yyyy HH:MM."""
        return format_datetime_italian(obj.created_at)
    creation_date_display.short_description = "Data creazione"

    def info_extra_details(self, obj):
        """Mostra info_e_costi, info_e_contatti da info_extra e cast dalla section."""
        style_label = (
            "display:block;font-size:0.75rem;font-weight:600;"
            "color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.25rem;"
        )
        style_value = (
            "display:block;white-space:pre-wrap;word-break:break-word;"
            "background:#f9fafb;border:1px solid #e5e7eb;border-radius:0.375rem;"
            "padding:0.5rem 0.75rem;font-size:0.875rem;color:#111827;margin-bottom:1rem;"
        )
        parts = []

        # Cast: primo valore trovato nella section (struttura: {chiave: {cast: "..."}})
        if obj.section:
            for section_data in obj.section.values():
                if isinstance(section_data, dict) and section_data.get("cast"):
                    parts.append(
                        f'<div><span style="{style_label}">Cast</span>'
                        f'<span style="{style_value}">{section_data["cast"]}</span></div>'
                    )
                    break

        # Info extra: info_e_costi e info_e_contatti
        if obj.info_extra:
            for key, label in [("info_e_costi", "Info e Costi"), ("info_e_contatti", "Info e Contatti")]:
                value = obj.info_extra.get(key)
                if value:
                    parts.append(
                        f'<div><span style="{style_label}">{label}</span>'
                        f'<span style="{style_value}">{value}</span></div>'
                    )

        return mark_safe("".join(parts)) if parts else "-"
    info_extra_details.short_description = "Dettagli Info Extra"

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
                'json_preview',
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
