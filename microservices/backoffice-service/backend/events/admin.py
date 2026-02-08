import json
from django import forms
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin
from django_ckeditor_5.widgets import CKEditor5Widget
from django_celery_results.models import TaskResult
from django_celery_results.admin import TaskResultAdmin as BaseTaskResultAdmin
from django.utils import timezone
from .models import ProductionEvent, StagingEvent
from comuni_italiani.models import ComuneItaliano, ProvinciaItaliana
from comuni_italiani.admin import ProvinciaFilter, RegioneFilter
from scraping.admin import CategoriaFilter


# =============================================================================
# Widget personalizzati per i campi del form
# =============================================================================

class CityAutocompleteWidget(forms.TextInput):
    """Campo testo con autocomplete che suggerisce i comuni italiani dal database."""
    template_name = 'admin/widgets/city_autocomplete.html'

    def get_context(self, name, value, attrs):
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
# Form per StagingEvent — definisce i widget per ogni campo
# =============================================================================

class StagingEventForm(forms.ModelForm):
    class Meta:
        model = StagingEvent
        fields = '__all__'
        widgets = {
            'title': forms.TextInput(attrs={'style': 'width: 100%;'}),
            'description': CKEditor5Widget(config_name='default'),
            'raw_data': forms.Textarea(attrs={'rows': 15, 'style': 'font-family: monospace; width: 100%;'}),
            'city': CityAutocompleteWidget(),
            'category': CategoryChipsWidget(),
            'location_name': forms.TextInput(attrs={'style': 'width: 100%;'}),
            'location_address': forms.TextInput(attrs={'style': 'width: 100%;'}),
            'price': forms.TextInput(attrs={'style': 'width: 100%;'}),
            'website': forms.URLInput(attrs={'style': 'width: 100%;'}),
        }


class ProductionEventForm(forms.ModelForm):
    class Meta:
        model = ProductionEvent
        fields = '__all__'
        widgets = {
            'title': forms.TextInput(attrs={'style': 'width: 100%;'}),
            'description': CKEditor5Widget(config_name='default'),
            'raw_data': forms.Textarea(attrs={'rows': 15, 'style': 'font-family: monospace; width: 100%;'}),
            'city': CityAutocompleteWidget(),
            'category': CategoryChipsWidget(),
            'location_name': forms.TextInput(attrs={'style': 'width: 100%;'}),
            'location_address': forms.TextInput(attrs={'style': 'width: 100%;'}),
            'price': forms.TextInput(attrs={'style': 'width: 100%;'}),
            'website': forms.URLInput(attrs={'style': 'width: 100%;'}),
        }


# =============================================================================
# Admin per StagingEvent — interfaccia a tab con Unfold
# =============================================================================

@admin.register(StagingEvent)
class StagingEventAdmin(ModelAdmin):
    form = StagingEventForm

    class Media:
        css = {
            'all': ('events/css/admin_custom.css',)
        }

    list_display = ['image_thumbnail', 'title', 'event_status_chip', 'category_list', 'city', 'source', 'loaded_at']
    list_display_links = ['title']
    list_filter = ['city', 'source', CategoriaFilter]
    search_fields = ['title', 'description', 'uuid']
    readonly_fields = [
        'loaded_at', 'image_preview', 'image_thumbnail', 'description_preview',
        'json_preview', 'clickable_url', 'clickable_image_url', 'source', 'uuid',
        'content_hash', 'category_list', 'date_start_display', 'date_start_ro', 'date_end_ro',
    ]
    list_per_page = 50

    fieldsets = (
        # Tab 1: Informazioni principali (source, uuid, date, titolo, luogo, url)
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">info</span> Informazioni Evento</span>'), {
            'fields': (
                ('source', 'uuid', 'date_start_ro', 'date_end_ro'),
                'title',
                ('city', 'location_address'),
                'location_name',
                'clickable_url',
            ),
            'classes': ['tab'],
        }),
        # Tab 2: Contenuto (descrizione, categorie, immagine, prezzo)
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">description</span> Contenuto</span>'), {
            'fields': (
                'description',
                'category',
                ('image_preview', 'clickable_image_url'),
                ('price', 'website'),
            ),
            'classes': ['tab'],
        }),
        # Tab 3: Date e orari (date editabili, orari, schedule)
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">calendar_month</span> Date e Orari</span>'), {
            'fields': (
                'date_start_display',
                ('date_start', 'date_end'),
                ('time_start', 'time_end'),
                ('time_info', 'schedule', 'weekdays'),
            ),
            'classes': ['tab'],
        }),
        # Tab 4: Dati tecnici (hash, raw JSON, timestamp)
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">code</span> Dati Tecnici</span>'), {
            'fields': (
                'content_hash',
                'json_preview',
                ('scraped_at', 'loaded_at'),
            ),
            'classes': ['tab'],
        }),
    )

    def event_status_chip(self, obj):
        """Mostra uno stato colorato: Verde (In corso), Rosso (Passato), Blu (Futuro)."""
        today = timezone.now().date()
        
        if not obj.date_start:
            return "-"
            
        start = obj.date_start
        end = obj.date_end if obj.date_end else start
        
        if end < today:
            # Passato - Rosso
            color, bg, label = '#991b1b', '#fee2e2', 'Passato'
        elif start <= today <= end:
            # In corso - Verde
            color, bg, label = '#166534', '#dcfce7', 'In corso'
        else:
            # Futuro - Blu
            color, bg, label = '#1e40af', '#dbeafe', 'Futuro'
            
        return format_html(
            '<span style="display:inline-block;padding:0.2rem 0.75rem;border-radius:9999px;'
            'font-size:0.75rem;font-weight:600;color:{};background:{};">{}</span>',
            color, bg, label
        )
    event_status_chip.short_description = "Stato"

    def category_list(self, obj):
        """Mostra le categorie come chip colorati nella lista e nel dettaglio."""
        if obj.category:
            chips = ''.join([
                f'<span style="display: inline-block; padding: 0.125rem 0.5rem; margin: 0.125rem; '
                f'background: #e0f2fe; color: #0369a1; border-radius: 9999px; font-size: 0.75rem; font-weight: 500;">'
                f'{cat}</span>'
                for cat in obj.category
            ])
            return mark_safe(f'<div style="display: flex; flex-wrap: wrap; gap: 0.125rem;">{chips}</div>')
        return "-"
    category_list.short_description = "Categorie"

    def clickable_url(self, obj):
        """Mostra l'URL sorgente come link cliccabile con icona di apertura esterna."""
        if obj.url:
            return format_html('<a href="{0}" target="_blank" class="text-primary-600 font-medium hover:underline flex items-center gap-1">{0} <span class="material-symbols-outlined text-sm">open_in_new</span></a>', obj.url)
        return "-"
    clickable_url.short_description = "URL Sorgente"

    def image_preview(self, obj):
        """Mostra un'anteprima dell'immagine nel dettaglio evento."""
        if obj.image_url:
            return format_html('<img src="{}" style="max-height: 100px; max-width: 150px; border-radius: 4px;" />', obj.image_url)
        return "-"
    image_preview.short_description = "Anteprima"

    def image_thumbnail(self, obj):
        """Mostra una miniatura cliccabile nella lista. Click apre popup a schermo intero."""
        if obj.image_url:
            return format_html(
                '<a href="javascript:void(0);" onclick="openImagePopup(\'{0}\')" style="cursor: pointer;">'
                '<img src="{0}" style="max-height: 60px; max-width: 80px; border-radius: 4px; object-fit: cover;" />'
                '</a>'
                '<script>'
                'if (!window.openImagePopup) {{'
                '  window.openImagePopup = function(url) {{'
                '    var overlay = document.createElement("div");'
                '    overlay.style.cssText = "position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:9999;display:flex;align-items:center;justify-content:center;cursor:pointer;";'
                '    overlay.onclick = function() {{ document.body.removeChild(overlay); }};'
                '    var img = document.createElement("img");'
                '    img.src = url;'
                '    img.style.cssText = "max-width:90%;max-height:90%;border-radius:8px;box-shadow:0 4px 20px rgba(0,0,0,0.5);";'
                '    overlay.appendChild(img);'
                '    document.body.appendChild(overlay);'
                '  }};'
                '}}'
                '</script>',
                obj.image_url
            )
        return "-"
    image_thumbnail.short_description = "Immagine"

    def description_preview(self, obj):
        """Renderizza la descrizione come HTML formattato (senza codice sorgente visibile)."""
        if obj.description:
            return mark_safe(obj.description)
        return "-"
    description_preview.short_description = "Anteprima Descrizione (HTML)"

    def json_preview(self, obj):
        """Mostra il campo raw_data come JSON con sintassi colorata (tema scuro) e pulsante copia."""
        if obj.raw_data:
            data = json.dumps(obj.raw_data, indent=2, sort_keys=True, ensure_ascii=False)
            unique_id = f"json-{obj.pk}-staging"
            fn = unique_id.replace('-', '_')
            return mark_safe(f'''
                <div style="position:relative;width:100%;">
                    <button type="button" onclick="{fn}_copy()"
                        style="position:absolute;top:8px;right:8px;padding:0.375rem 0.75rem;
                        background:#2563eb;color:#fff;border:none;border-radius:0.375rem;
                        cursor:pointer;font-size:0.75rem;display:flex;align-items:center;gap:0.25rem;z-index:1;"
                        onmouseover="this.style.background='#1d4ed8'"
                        onmouseout="this.style.background='#2563eb'">
                        <span class="material-symbols-outlined" style="font-size:1rem;">content_copy</span> Copia
                    </button>
                    <pre id="{unique_id}" style="white-space:pre-wrap;word-wrap:break-word;
                        background:#1e1e2e;color:#cdd6f4;padding:2.5rem 1rem 1rem;
                        border-radius:0.5rem;font-family:'Fira Code',Consolas,monospace;
                        font-size:0.8rem;line-height:1.6;width:100%;box-sizing:border-box;
                        overflow-x:auto;"></pre>
                </div>
                <script>
                (function() {{
                    var raw = {json.dumps(data)};
                    var el = document.getElementById("{unique_id}");
                    el.innerHTML = raw
                        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                        .replace(/"([^"]+)"\\s*:/g, '<span style="color:#89b4fa;">"$1"</span>:')
                        .replace(/:\\s*"([^"]*)"/g, ': <span style="color:#a6e3a1;">"$1"</span>')
                        .replace(/:\\s*(\\d+\\.?\\d*)/g, ': <span style="color:#fab387;">$1</span>')
                        .replace(/:\\s*(true|false)/g, ': <span style="color:#f38ba8;">$1</span>')
                        .replace(/:\\s*(null)/g, ': <span style="color:#6c7086;">$1</span>');
                }})();
                function {fn}_copy() {{
                    var raw = {json.dumps(data)};
                    navigator.clipboard.writeText(raw).then(function() {{
                        var btn = event.target.closest("button");
                        var orig = btn.innerHTML;
                        btn.innerHTML = '<span class="material-symbols-outlined" style="font-size:1rem;">check</span> Copiato!';
                        btn.style.background = '#16a34a';
                        setTimeout(function() {{ btn.innerHTML = orig; btn.style.background = '#2563eb'; }}, 2000);
                    }});
                }}
                </script>
            ''')
        return "-"
    json_preview.short_description = "Raw Data"

    def clickable_image_url(self, obj):
        """Mostra l'URL dell'immagine come link cliccabile con word-break per URL lunghi."""
        if obj.image_url:
            return format_html(
                '<div style="min-width: 600px; display: inline-block;">'
                '<a href="{0}" target="_blank" class="text-primary-600 font-medium hover:underline flex items-center gap-1" style="word-break: break-all;">'
                '{0} <span class="material-symbols-outlined text-sm">open_in_new</span></a></div>',
                obj.image_url
            )
        return "-"
    clickable_image_url.short_description = "URL Immagine"

    def date_start_display(self, obj):
        """Mostra la data di inizio in formato italiano (dd/mm/yyyy) — sola lettura."""
        if obj.date_start:
            return obj.date_start.strftime('%d/%m/%Y')
        return "-"
    date_start_display.short_description = "Data Inizio"

    def date_start_ro(self, obj):
        """Copia readonly di date_start per il Tab 1 (le date editabili sono nel Tab 3)."""
        if obj.date_start:
            return obj.date_start.strftime('%d/%m/%Y')
        return "-"
    date_start_ro.short_description = "Data Inizio"

    def date_end_ro(self, obj):
        """Copia readonly di date_end per il Tab 1 (le date editabili sono nel Tab 3)."""
        if obj.date_end:
            return obj.date_end.strftime('%d/%m/%Y')
        return "-"
    date_end_ro.short_description = "Data Fine"


# =============================================================================
# Admin per ProductionEvent — interfaccia a tab con Unfold
# =============================================================================

@admin.register(ProductionEvent)
class ProductionEventAdmin(ModelAdmin):
    form = ProductionEventForm

    class Media:
        css = {
            'all': ('events/css/admin_custom.css',)
        }

    list_display = ['image_thumbnail', 'title', 'event_status_chip', 'category_list', 'city', 'source', 'date_start', 'is_active']
    list_display_links = ['title']
    list_filter = ['is_active', 'city', 'source', CategoriaFilter]
    search_fields = ['title', 'description', 'uuid']
    readonly_fields = [
        'created_at', 'updated_at', 'image_preview', 'image_thumbnail', 'description_preview',
        'json_preview', 'clickable_url', 'clickable_image_url', 'source', 'uuid',
        'content_hash', 'category_list', 'date_start_display', 'date_start_ro', 'date_end_ro',
    ]
    list_per_page = 50

    fieldsets = (
        # Tab 1: Informazioni principali
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
        # Tab 2: Contenuto
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">description</span> Contenuto</span>'), {
            'fields': (
                'description',
                'category',
                ('image_preview', 'clickable_image_url'),
                ('price', 'website'),
            ),
            'classes': ['tab'],
        }),
        # Tab 3: Date e orari
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">calendar_month</span> Date e Orari</span>'), {
            'fields': (
                'date_start_display',
                ('date_start', 'date_end'),
                ('time_start', 'time_end'),
                ('time_info', 'schedule', 'weekdays'),
            ),
            'classes': ['tab'],
        }),
        # Tab 4: Dati tecnici
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">code</span> Dati Tecnici</span>'), {
            'fields': (
                'content_hash',
                'json_preview',
                ('scraped_at', 'created_at', 'updated_at'),
            ),
            'classes': ['tab'],
        }),
    )

    def event_status_chip(self, obj):
        """Mostra uno stato colorato: Verde (In corso), Rosso (Passato), Blu (Futuro)."""
        today = timezone.now().date()
        
        if not obj.date_start:
            return "-"
            
        start = obj.date_start
        end = obj.date_end if obj.date_end else start
        
        if end < today:
            # Passato - Rosso
            color, bg, label = '#991b1b', '#fee2e2', 'Passato'
        elif start <= today <= end:
            # In corso - Verde
            color, bg, label = '#166534', '#dcfce7', 'In corso'
        else:
            # Futuro - Blu
            color, bg, label = '#1e40af', '#dbeafe', 'Futuro'
            
        return format_html(
            '<span style="display:inline-block;padding:0.2rem 0.75rem;border-radius:9999px;'
            'font-size:0.75rem;font-weight:600;color:{};background:{};">{}</span>',
            color, bg, label
        )
    event_status_chip.short_description = "Stato"

    def category_list(self, obj):
        if obj.category:
            chips = ''.join([
                f'<span style="display: inline-block; padding: 0.125rem 0.5rem; margin: 0.125rem; '
                f'background: #e0f2fe; color: #0369a1; border-radius: 9999px; font-size: 0.75rem; font-weight: 500;">'
                f'{cat}</span>'
                for cat in obj.category
            ])
            return mark_safe(f'<div style="display: flex; flex-wrap: wrap; gap: 0.125rem;">{chips}</div>')
        return "-"
    category_list.short_description = "Categorie"

    def clickable_url(self, obj):
        if obj.url:
            return format_html('<a href="{0}" target="_blank" class="text-primary-600 font-medium hover:underline flex items-center gap-1">{0} <span class="material-symbols-outlined text-sm">open_in_new</span></a>', obj.url)
        return "-"
    clickable_url.short_description = "URL Sorgente"

    def image_preview(self, obj):
        if obj.image_url:
            return format_html('<img src="{}" style="max-height: 100px; max-width: 150px; border-radius: 4px;" />', obj.image_url)
        return "-"
    image_preview.short_description = "Anteprima"

    def image_thumbnail(self, obj):
        if obj.image_url:
            return format_html(
                '<a href="javascript:void(0);" onclick="openImagePopup(\'{0}\')" style="cursor: pointer;">'
                '<img src="{0}" style="max-height: 60px; max-width: 80px; border-radius: 4px; object-fit: cover;" />'
                '</a>'
                '<script>'
                'if (!window.openImagePopup) {{'
                '  window.openImagePopup = function(url) {{'
                '    var overlay = document.createElement("div");'
                '    overlay.style.cssText = "position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:9999;display:flex;align-items:center;justify-content:center;cursor:pointer;";'
                '    overlay.onclick = function() {{ document.body.removeChild(overlay); }};'
                '    var img = document.createElement("img");'
                '    img.src = url;'
                '    img.style.cssText = "max-width:90%;max-height:90%;border-radius:8px;box-shadow:0 4px 20px rgba(0,0,0,0.5);";'
                '    overlay.appendChild(img);'
                '    document.body.appendChild(overlay);'
                '  }};'
                '}}'
                '</script>',
                obj.image_url
            )
        return "-"
    image_thumbnail.short_description = "Immagine"

    def description_preview(self, obj):
        if obj.description:
            return mark_safe(obj.description)
        return "-"
    description_preview.short_description = "Anteprima Descrizione (HTML)"

    def json_preview(self, obj):
        if obj.raw_data:
            data = json.dumps(obj.raw_data, indent=2, sort_keys=True, ensure_ascii=False)
            unique_id = f"json-{obj.pk}-production"
            fn = unique_id.replace('-', '_')
            return mark_safe(f'''
                <div style="position:relative;width:100%;">
                    <button type="button" onclick="{fn}_copy()"
                        style="position:absolute;top:8px;right:8px;padding:0.375rem 0.75rem;
                        background:#2563eb;color:#fff;border:none;border-radius:0.375rem;
                        cursor:pointer;font-size:0.75rem;display:flex;align-items:center;gap:0.25rem;z-index:1;"
                        onmouseover="this.style.background='#1d4ed8'"
                        onmouseout="this.style.background='#2563eb'">
                        <span class="material-symbols-outlined" style="font-size:1rem;">content_copy</span> Copia
                    </button>
                    <pre id="{unique_id}" style="white-space:pre-wrap;word-wrap:break-word;
                        background:#1e1e2e;color:#cdd6f4;padding:2.5rem 1rem 1rem;
                        border-radius:0.5rem;font-family:'Fira Code',Consolas,monospace;
                        font-size:0.8rem;line-height:1.6;width:100%;box-sizing:border-box;
                        overflow-x:auto;"></pre>
                </div>
                <script>
                (function() {{
                    var raw = {json.dumps(data)};
                    var el = document.getElementById("{unique_id}");
                    el.innerHTML = raw
                        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                        .replace(/"([^"]+)"\\s*:/g, '<span style="color:#89b4fa;">"$1"</span>:')
                        .replace(/:\\s*"([^"]*)"/g, ': <span style="color:#a6e3a1;">"$1"</span>')
                        .replace(/:\\s*(\\d+\\.?\\d*)/g, ': <span style="color:#fab387;">$1</span>')
                        .replace(/:\\s*(true|false)/g, ': <span style="color:#f38ba8;">$1</span>')
                        .replace(/:\\s*(null)/g, ': <span style="color:#6c7086;">$1</span>');
                }})();
                function {fn}_copy() {{
                    var raw = {json.dumps(data)};
                    navigator.clipboard.writeText(raw).then(function() {{
                        var btn = event.target.closest("button");
                        var orig = btn.innerHTML;
                        btn.innerHTML = '<span class="material-symbols-outlined" style="font-size:1rem;">check</span> Copiato!';
                        btn.style.background = '#16a34a';
                        setTimeout(function() {{ btn.innerHTML = orig; btn.style.background = '#2563eb'; }}, 2000);
                    }});
                }}
                </script>
            ''')
        return "-"
    json_preview.short_description = "Raw Data"

    def clickable_image_url(self, obj):
        if obj.image_url:
            return format_html(
                '<div style="min-width: 600px; display: inline-block;">'
                '<a href="{0}" target="_blank" class="text-primary-600 font-medium hover:underline flex items-center gap-1" style="word-break: break-all;">'
                '{0} <span class="material-symbols-outlined text-sm">open_in_new</span></a></div>',
                obj.image_url
            )
        return "-"
    clickable_image_url.short_description = "URL Immagine"

    def date_start_display(self, obj):
        if obj.date_start:
            return obj.date_start.strftime('%d/%m/%Y')
        return "-"
    date_start_display.short_description = "Data Inizio"

    def date_start_ro(self, obj):
        if obj.date_start:
            return obj.date_start.strftime('%d/%m/%Y')
        return "-"
    date_start_ro.short_description = "Data Inizio"

    def date_end_ro(self, obj):
        if obj.date_end:
            return obj.date_end.strftime('%d/%m/%Y')
        return "-"
    date_end_ro.short_description = "Data Fine"


# =============================================================================
# Admin per Celery Task Results — chip colorati per lo stato
# =============================================================================

STATUS_COLORS = {
    'SUCCESS': ('#065f46', '#d1fae5'),   # verde
    'FAILURE': ('#991b1b', '#fee2e2'),   # rosso
    'PENDING': ('#92400e', '#fef3c7'),   # arancio
    'STARTED': ('#92400e', '#fef3c7'),   # arancio
    'RETRY':   ('#92400e', '#fef3c7'),   # arancio
    'REVOKED': ('#991b1b', '#fee2e2'),   # rosso
}

admin.site.unregister(TaskResult)


@admin.register(TaskResult)
class CustomTaskResultAdmin(BaseTaskResultAdmin, ModelAdmin):
    """Admin personalizzato per i risultati dei task Celery con chip colorati per stato."""
    list_display = ['task_id', 'task_name', 'status_chip', 'task_kwargs', 'date_done']

    def status_chip(self, obj):
        """Mostra lo stato del task come chip colorato: verde=SUCCESS, rosso=FAILURE, arancio=altri."""
        color, bg = STATUS_COLORS.get(obj.status, ('#92400e', '#fef3c7'))
        return format_html(
            '<span style="display:inline-block;padding:0.2rem 0.75rem;border-radius:9999px;'
            'font-size:0.75rem;font-weight:600;color:{};background:{};">{}</span>',
            color, bg, obj.status,
        )
    status_chip.short_description = "Status"
