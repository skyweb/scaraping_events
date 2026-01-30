import json
from django import forms
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin
from unfold.contrib.forms.widgets import WysiwygWidget
from unfold.contrib.filters.admin import RangeDateFilter
from django.contrib.admin import SimpleListFilter
from .models import ProductionEvent, StagingEvent, EtlRun, EtlError, ComuneItaliano, ProvinciaItaliana, ScrapingCategoria, ScrapingLocation


class ProvinciaFilter(SimpleListFilter):
    title = 'Provincia'
    parameter_name = 'provincia'

    def lookups(self, request, model_admin):
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute('SELECT sigla, den_uts FROM comuni_italiani.province ORDER BY den_uts')
            return [(row[0], f"{row[1]} ({row[0]})") for row in cursor.fetchall()]

    def queryset(self, request, queryset):
        if self.value():
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute('SELECT cod_uts FROM comuni_italiani.province WHERE sigla = %s', [self.value()])
                row = cursor.fetchone()
                if row:
                    return queryset.filter(cod_uts=row[0])
        return queryset


class RegioneFilter(SimpleListFilter):
    title = 'Regione'
    parameter_name = 'regione'

    def lookups(self, request, model_admin):
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute('SELECT cod_reg, den_reg FROM comuni_italiani.regioni ORDER BY den_reg')
            return [(row[0], row[1]) for row in cursor.fetchall()]

    def queryset(self, request, queryset):
        if self.value():
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute('SELECT cod_uts FROM comuni_italiani.province WHERE cod_reg = %s', [self.value()])
                cod_uts_list = [row[0] for row in cursor.fetchall()]
                if cod_uts_list:
                    return queryset.filter(cod_uts__in=cod_uts_list)
        return queryset


class CategoriaFilter(SimpleListFilter):
    title = 'Categoria'
    parameter_name = 'categoria'

    def lookups(self, request, model_admin):
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT DISTINCT unnest(category) as cat
                FROM events_data.staging_events
                WHERE category IS NOT NULL
                ORDER BY cat
            ''')
            return [(row[0], row[0]) for row in cursor.fetchall()]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(category__contains=[self.value()])
        return queryset


class CustomWysiwygWidget(WysiwygWidget):
    class Media:
        css = {
            'all': ('https://unpkg.com/trix@2.0.8/dist/trix.css',)
        }
        js = ('https://unpkg.com/trix@2.0.8/dist/trix.umd.min.js',)


class CityAutocompleteWidget(forms.TextInput):
    """Widget con autocomplete per i comuni italiani"""
    template_name = 'admin/widgets/city_autocomplete.html'

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['comuni'] = ComuneItaliano.objects.values_list('comune', flat=True)
        return context


class CategoryChipsWidget(forms.TextInput):
    """Widget che mostra le categorie come chip editabili"""
    template_name = 'admin/widgets/category_chips.html'

    def format_value(self, value):
        if value is None:
            return ''
        if isinstance(value, list):
            return ','.join(value)
        return value

    def value_from_datadict(self, data, files, name):
        value = data.get(name, '')
        if value:
            return [v.strip() for v in value.split(',') if v.strip()]
        return []


class ProductionEventForm(forms.ModelForm):
    class Meta:
        model = ProductionEvent
        fields = '__all__'
        widgets = {
            'description': CustomWysiwygWidget,
            'raw_data': forms.Textarea(attrs={'rows': 15, 'style': 'font-family: monospace; width: 100%;'}),
            'city': CityAutocompleteWidget(),
            'category': CategoryChipsWidget(),
            'location_name': forms.TextInput(attrs={'style': 'width: 100%;'}),
            'location_address': forms.TextInput(attrs={'style': 'width: 100%;'}),
        }


class StagingEventForm(forms.ModelForm):
    class Meta:
        model = StagingEvent
        fields = '__all__'
        widgets = {
            'description': CustomWysiwygWidget,
            'raw_data': forms.Textarea(attrs={'rows': 15, 'style': 'font-family: monospace; width: 100%;'}),
            'city': CityAutocompleteWidget(),
            'category': CategoryChipsWidget(),
            'location_name': forms.TextInput(attrs={'style': 'width: 100%;'}),
            'location_address': forms.TextInput(attrs={'style': 'width: 100%;'}),
        }


@admin.register(ProductionEvent)
class ProductionEventAdmin(ModelAdmin):
    form = ProductionEventForm
    list_display = ['title', 'city', 'source', 'date_start', 'date_end', 'is_active']
    list_filter = [
        'is_active',
        'city',
        'source',
        ('date_start', RangeDateFilter),
    ]
    list_filter_submit = True
    search_fields = ['title', 'description', 'location_name']
    readonly_fields = ['uuid', 'content_hash', 'created_at', 'updated_at', 'scraped_at', 'description_preview', 'json_preview', 'clickable_url', 'clickable_image_url']
    ordering = ['-date_start']
    list_per_page = 25

    fieldsets = (
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">info</span> Informazioni Evento</span>'), {
            'fields': (
                'title',
                ('source', 'uuid', 'content_hash'),  # 3 campi affiancati
                'clickable_url',
            ),
            'classes': ['tab'],
        }),
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">description</span> Contenuto</span>'), {
            'fields': (
                'description_preview',
                'category',
                'clickable_image_url',
            ),
            'classes': ['tab'],
        }),
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">location_on</span> Luogo</span>'), {
            'fields': (
                ('city', 'location_name', 'location_address'),  # 3 campi affiancati
            ),
            'classes': ['tab'],
        }),
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">calendar_month</span> Date e Orari</span>'), {
            'fields': (
                ('date_start', 'date_end'),      # date affiancate
                ('time_start', 'time_end'),      # orari affiancati
                'time_info',
                ('schedule', 'weekdays'),        # affiancati
            ),
            'classes': ['tab'],
        }),
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">more_horiz</span> Info Aggiuntive</span>'), {
            'fields': (
                ('price', 'website'),            # affiancati
                ('raw_data', 'json_preview'),
            ),
            'classes': ['tab'],
        }),
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">toggle_on</span> Stato</span>'), {
            'fields': (
                'is_active',
                ('scraped_at', 'created_at', 'updated_at'),  # 3 timestamp affiancati
            ),
            'classes': ['tab'],
        }),
    )

    def clickable_url(self, obj):
        if obj.url:
            return format_html('<a href="{0}" target="_blank" class="text-primary-600 font-medium hover:underline flex items-center gap-1">{0} <span class="material-symbols-outlined text-sm">open_in_new</span></a>', obj.url)
        return "-"
    clickable_url.short_description = "URL Sorgente"

    def description_preview(self, obj):
        if obj.description:
            return mark_safe(obj.description)
        return "-"
    description_preview.short_description = "Anteprima Descrizione (HTML)"

    def json_preview(self, obj):
        if obj.raw_data:
            data = json.dumps(obj.raw_data, indent=4, sort_keys=True, ensure_ascii=False)
            unique_id = f"json-{obj.pk}-prod"
            return mark_safe(f'''
                <div style="position: relative;">
                    <button type="button" onclick="copyJson_{unique_id.replace('-', '_')}()"
                        style="position: absolute; top: 8px; right: 8px; padding: 0.375rem 0.75rem;
                        background: #2563eb; color: white; border: none; border-radius: 0.375rem;
                        cursor: pointer; font-size: 0.75rem; display: flex; align-items: center; gap: 0.25rem;"
                        onmouseover="this.style.background='#1d4ed8'"
                        onmouseout="this.style.background='#2563eb'">
                        <span class="material-symbols-outlined" style="font-size: 1rem;">content_copy</span> Copia
                    </button>
                    <pre id="{unique_id}" style="white-space: pre-wrap; word-wrap: break-word; background: #f8f9fa; padding: 10px; padding-top: 40px; border-radius: 4px; border: 1px solid #dee2e6;">{data}</pre>
                </div>
                <script>
                function copyJson_{unique_id.replace('-', '_')}() {{
                    var text = document.getElementById("{unique_id}").innerText;
                    navigator.clipboard.writeText(text).then(function() {{
                        var btn = event.target.closest("button");
                        var originalHtml = btn.innerHTML;
                        btn.innerHTML = '<span class="material-symbols-outlined" style="font-size: 1rem;">check</span> Copiato!';
                        btn.style.background = '#16a34a';
                        setTimeout(function() {{
                            btn.innerHTML = originalHtml;
                            btn.style.background = '#2563eb';
                        }}, 2000);
                    }});
                }}
                </script>
            ''')
        return "-"
    json_preview.short_description = "Anteprima JSON Formattata"

    def clickable_image_url(self, obj):
        if obj.image_url:
            return format_html(
                '<div style="min-width: 50%; display: inline-block;">'
                '<a href="{0}" target="_blank" class="text-primary-600 font-medium hover:underline flex items-center gap-1" style="word-break: break-all;">'
                '{0} <span class="material-symbols-outlined text-sm">open_in_new</span></a></div>',
                obj.image_url
            )
        return "-"
    clickable_image_url.short_description = "URL Immagine"


@admin.register(StagingEvent)
class StagingEventAdmin(ModelAdmin):
    form = StagingEventForm
    list_display = ['image_thumbnail', 'title', 'category_list', 'city', 'source', 'loaded_at']
    list_display_links = ['title']
    list_filter = ['city', 'source', CategoriaFilter]
    search_fields = ['title', 'description']
    readonly_fields = ['loaded_at', 'image_preview', 'image_thumbnail', 'description_preview', 'json_preview', 'clickable_url', 'clickable_image_url', 'source', 'uuid', 'content_hash', 'category_list', 'date_start_display']
    list_per_page = 25

    fieldsets = (
        # Tab 1: Informazioni principali
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">info</span> Informazioni Evento</span>'), {
            'fields': (
                ('source', 'uuid', 'date_start_display'),
                'title',
                ('city', 'location_name', 'location_address'),
                'clickable_url',
            ),
            'classes': ['tab'],
        }),
        # Tab 2: Contenuto
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">description</span> Contenuto</span>'), {
            'fields': (
                'description',
                'category',
                'image_preview',
                ('price', 'website','clickable_image_url'),         # price e website affiancati
            ),
            'classes': ['tab'],
        }),
        # Tab 3: Date e orari
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">calendar_month</span> Date e Orari</span>'), {
            'fields': (
                ('date_start', 'date_end'),   # date affiancate
                ('time_start', 'time_end'),   # orari affiancati
                ('time_info','schedule', 'weekdays'),     # schedule e weekdays affiancati
            ),
            'classes': ['tab'],
        }),
        # Tab 4: Dati tecnici
        (mark_safe('<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><span class="material-symbols-outlined">code</span> Dati Tecnici</span>'), {
            'fields': (
                'content_hash',
                'json_preview',
                ('scraped_at', 'loaded_at'),  # timestamp affiancati
            ),
            'classes': ['tab'],
        }),
    )

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
            data = json.dumps(obj.raw_data, indent=4, sort_keys=True, ensure_ascii=False)
            unique_id = f"json-{obj.pk}-staging"
            return mark_safe(f'''
                <div style="position: relative;">
                    <button type="button" onclick="copyJson_{unique_id.replace('-', '_')}()"
                        style="position: absolute; top: 8px; right: 8px; padding: 0.375rem 0.75rem;
                        background: #2563eb; color: white; border: none; border-radius: 0.375rem;
                        cursor: pointer; font-size: 0.75rem; display: flex; align-items: center; gap: 0.25rem;"
                        onmouseover="this.style.background='#1d4ed8'"
                        onmouseout="this.style.background='#2563eb'">
                        <span class="material-symbols-outlined" style="font-size: 1rem;">content_copy</span> Copia
                    </button>
                    <pre id="{unique_id}" style="white-space: pre-wrap; word-wrap: break-word; background: #f8f9fa; padding: 10px; padding-top: 40px; border-radius: 4px; border: 1px solid #dee2e6;">{data}</pre>
                </div>
                <script>
                function copyJson_{unique_id.replace('-', '_')}() {{
                    var text = document.getElementById("{unique_id}").innerText;
                    navigator.clipboard.writeText(text).then(function() {{
                        var btn = event.target.closest("button");
                        var originalHtml = btn.innerHTML;
                        btn.innerHTML = '<span class="material-symbols-outlined" style="font-size: 1rem;">check</span> Copiato!';
                        btn.style.background = '#16a34a';
                        setTimeout(function() {{
                            btn.innerHTML = originalHtml;
                            btn.style.background = '#2563eb';
                        }}, 2000);
                    }});
                }}
                </script>
            ''')
        return "-"
    json_preview.short_description = "Anteprima JSON Formattata"

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


@admin.register(EtlRun)
class EtlRunAdmin(ModelAdmin):
    list_display = ['run_type', 'source', 'status', 'staging_count', 'inserted_count', 'updated_count', 'started_at']
    list_filter = ['run_type', 'source', 'status']
    readonly_fields = ['started_at', 'staging_completed_at', 'upsert_completed_at']
    ordering = ['-started_at']
    list_per_page = 25


@admin.register(EtlError)
class EtlErrorAdmin(ModelAdmin):
    list_display = ['error_type', 'source', 'json_file', 'created_at']
    list_filter = ['error_type', 'source']
    search_fields = ['error_message', 'json_file']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    list_per_page = 25


@admin.register(ComuneItaliano)
class ComuneItalianoAdmin(ModelAdmin):
    list_display = ['comune', 'sigla_provincia', 'nome_regione', 'codice_istat']
    list_filter = [RegioneFilter, ProvinciaFilter]
    list_filter_submit = True
    search_fields = ['comune', 'cap', 'codice_catastale', 'pro_com_t']
    ordering = ['comune']
    list_per_page = 50
    readonly_fields = ['map_preview', 'codice_istat', 'sigla_provincia', 'nome_regione']
    exclude = ['geom', 'centroid', 'pro_com_t', 'cod_uts']

    fieldsets = (
        ('Informazioni', {
            'fields': (
                ('comune','sigla_provincia', 'nome_regione'),
                ('codice_catastale', 'codice_istat','cap'),
                ('popolazione'),
            ),
        }),
        ('Confini', {
            'fields': ('map_preview',),
        }),
    )

    def codice_istat(self, obj):
        return obj.pro_com_t or "-"
    codice_istat.short_description = "Codice ISTAT"

    def sigla_provincia(self, obj):
        from django.db import connection
        if obj.cod_uts:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT sigla FROM comuni_italiani.province WHERE cod_uts = %s',
                    [obj.cod_uts]
                )
                row = cursor.fetchone()
                return row[0] if row else "-"
        return "-"
    sigla_provincia.short_description = "Provincia"

    def nome_regione(self, obj):
        from django.db import connection
        if obj.cod_uts:
            with connection.cursor() as cursor:
                cursor.execute('''
                    SELECT r.den_reg
                    FROM comuni_italiani.province p
                    JOIN comuni_italiani.regioni r ON p.cod_reg = r.cod_reg
                    WHERE p.cod_uts = %s
                ''', [obj.cod_uts])
                row = cursor.fetchone()
                return row[0] if row else "-"
        return "-"
    nome_regione.short_description = "Regione"

    def map_preview(self, obj):
        from django.db import connection
        from urllib.parse import quote
        import json as json_lib

        # Query per ottenere GeoJSON dei confini
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT ST_AsGeoJSON(ST_Transform(geom, 4326)) FROM comuni_italiani.comuni WHERE comune = %s',
                [obj.pk]
            )
            row = cursor.fetchone()
            geojson = row[0] if row and row[0] else None

        # Query per ottenere il centroide
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT ST_AsGeoJSON(ST_Transform(centroid, 4326)) FROM comuni_italiani.comuni WHERE comune = %s',
                [obj.pk]
            )
            row = cursor.fetchone()
            centroid = row[0] if row and row[0] else None

        # Query per ottenere i comuni confinanti con le loro geometrie
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT c2.comune, ST_AsGeoJSON(ST_Transform(c2.geom, 4326))
                FROM comuni_italiani.comuni c1, comuni_italiani.comuni c2
                WHERE c1.comune = %s
                AND ST_Touches(c1.geom, c2.geom)
                AND c1.comune != c2.comune
                ORDER BY c2.comune
            ''', [obj.pk])
            confinanti = cursor.fetchall()

        # Lista comuni confinanti con link
        if confinanti:
            lista_items = ''.join([
                f'<li style="margin-bottom: 0.5rem;">'
                f'<a href="/admin/events/comuneitaliano/{quote(nome)}/change/" '
                f'style="color: #2563eb; text-decoration: none; font-weight: 500;" '
                f'onmouseover="this.style.textDecoration=\'underline\'" '
                f'onmouseout="this.style.textDecoration=\'none\'">'
                f'{nome}</a></li>'
                for nome, geom in confinanti
            ])
            confinanti_html = f'''
                <div style="min-width: 250px; max-width: 300px;">
                    <div style="font-weight: 600; color: #374151; margin-bottom: 0.75rem; font-size: 1rem;">
                        Comuni confinanti ({len(confinanti)})
                    </div>
                    <ul style="list-style-type: disc; padding-left: 1.25rem; margin: 0; max-height: 400px; overflow-y: auto;">
                        {lista_items}
                    </ul>
                </div>
            '''
            # Prepara array JSON dei comuni confinanti per la mappa
            confinanti_geojson = json_lib.dumps([
                {"nome": nome, "geom": json_lib.loads(geom)} for nome, geom in confinanti if geom
            ])
        else:
            confinanti_html = '''
                <div style="min-width: 250px;">
                    <div style="font-weight: 600; color: #374151; margin-bottom: 0.5rem;">Comuni confinanti</div>
                    <em style="color: #6b7280;">Nessun comune confinante trovato</em>
                </div>
            '''
            confinanti_geojson = '[]'

        if geojson:
            centroid_js = f'var centroid = {centroid};' if centroid else 'var centroid = null;'
            return mark_safe(f'''
                <div style="display: flex; gap: 1.5rem; align-items: flex-start;">
                    {confinanti_html}
                    <div style="flex: 1;">
                        <div style="margin-bottom: 0.5rem;">
                            <label style="display: inline-flex; align-items: center; gap: 0.5rem; cursor: pointer; user-select: none;">
                                <input type="checkbox" id="toggle-confinanti-{obj.pk}"
                                    style="width: 1rem; height: 1rem; cursor: pointer;">
                                <span style="font-size: 0.875rem; color: #374151;">Mostra confini</span>
                            </label>
                        </div>
                        <div id="map-comune-{obj.pk}" style="height: 450px; width: 100%; border-radius: 8px; border: 1px solid #e5e7eb;"></div>
                    </div>
                </div>
                <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
                <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
                <script>
                (function() {{
                    setTimeout(function() {{
                        var mapEl = document.getElementById("map-comune-{obj.pk}");
                        if (!mapEl || mapEl._leaflet_id) return;

                        var map = L.map("map-comune-{obj.pk}").setView([42.5, 12.5], 6);

                        // Layer di base
                        var osm = L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
                            attribution: "&copy; OpenStreetMap"
                        }});

                        var satellite = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}", {{
                            attribution: "&copy; Esri"
                        }});

                        var terrain = L.tileLayer("https://{{s}}.tile.opentopomap.org/{{z}}/{{x}}/{{y}}.png", {{
                            attribution: "&copy; OpenTopoMap"
                        }});

                        var cartoLight = L.tileLayer("https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png", {{
                            attribution: "&copy; CartoDB"
                        }});

                        // Aggiungi layer di default
                        osm.addTo(map);

                        // Controllo layer
                        var baseMaps = {{
                            "Stradale": osm,
                            "Satellite": satellite,
                            "Terreno": terrain,
                            "Chiaro": cartoLight
                        }};

                        L.control.layers(baseMaps, null, {{ position: 'topright' }}).addTo(map);

                        // Gruppo per tutti i layer (per calcolare i bounds)
                        var allLayers = L.featureGroup();
                        var confinantiLayers = L.featureGroup();

                        // Comuni confinanti (blu)
                        var confinantiData = {confinanti_geojson};
                        confinantiData.forEach(function(c) {{
                            var confinanteLayer = L.geoJSON(c.geom, {{
                                style: {{
                                    color: "#2563eb",
                                    weight: 2,
                                    fillColor: "#3b82f6",
                                    fillOpacity: 0.15
                                }}
                            }});
                            confinanteLayer.bindPopup("<strong>" + c.nome + "</strong>");
                            confinantiLayers.addLayer(confinanteLayer);
                            allLayers.addLayer(confinanteLayer);
                        }});

                        // Confini del comune principale (verde)
                        var geojson = {geojson};
                        var layer = L.geoJSON(geojson, {{
                            style: {{
                                color: "#16a34a",
                                weight: 3,
                                fillColor: "#22c55e",
                                fillOpacity: 0.3
                            }}
                        }}).addTo(map);
                        allLayers.addLayer(layer);

                        // Centroide
                        {centroid_js}
                        if (centroid && centroid.coordinates) {{
                            var centroidMarker = L.circleMarker(
                                [centroid.coordinates[1], centroid.coordinates[0]],
                                {{
                                    radius: 8,
                                    fillColor: "#dc2626",
                                    color: "#fff",
                                    weight: 2,
                                    opacity: 1,
                                    fillOpacity: 0.9
                                }}
                            ).addTo(map);
                            centroidMarker.bindPopup("<strong>Centroide</strong><br>{obj.comune}");
                        }}

                        // Zoom per includere tutti i comuni (principale + confinanti)
                        map.fitBounds(allLayers.getBounds(), {{ padding: [30, 30] }});

                        // Toggle checkbox per mostrare/nascondere comuni confinanti
                        var checkbox = document.getElementById("toggle-confinanti-{obj.pk}");
                        checkbox.addEventListener("change", function() {{
                            if (this.checked) {{
                                confinantiLayers.addTo(map);
                            }} else {{
                                map.removeLayer(confinantiLayers);
                            }}
                        }});
                    }}, 200);
                }})();
                </script>
            ''')
        return mark_safe(f'<div style="display: flex; gap: 1.5rem;">{confinanti_html}<em>Nessuna geometria disponibile</em></div>')
    map_preview.short_description = "Mappa Confini"


@admin.register(ProvinciaItaliana)
class ProvinciaItalianaAdmin(ModelAdmin):
    list_display = ['denominazione', 'sigla', 'tipologia']

    def denominazione(self, obj):
        return obj.den_uts
    denominazione.short_description = "Provincia"
    denominazione.admin_order_field = 'den_uts'

    def tipologia(self, obj):
        return obj.tipo_uts
    tipologia.short_description = "Tipologia"
    tipologia.admin_order_field = 'tipo_uts'

    list_filter = ['tipo_uts']
    search_fields = ['den_uts', 'sigla']
    ordering = ['den_uts']
    list_per_page = 50
    readonly_fields = ['map_preview', 'denominazione']
    exclude = ['geom', 'shape_area', 'den_uts']

    fieldsets = (
        ('Informazioni', {
            'fields': ('denominazione', 'sigla', 'tipo_uts'),
        }),
        ('Confini', {
            'fields': ('map_preview',),
        }),
    )

    def map_preview(self, obj):
        from django.db import connection

        # Query per ottenere GeoJSON da PostGIS
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT ST_AsGeoJSON(ST_Transform(geom, 4326)) FROM comuni_italiani.province WHERE den_uts = %s',
                [obj.pk]
            )
            row = cursor.fetchone()
            geojson = row[0] if row and row[0] else None

        # Query per ottenere le province confinanti
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT p2.den_uts, p2.sigla
                FROM comuni_italiani.province p1, comuni_italiani.province p2
                WHERE p1.den_uts = %s
                AND ST_Touches(p1.geom, p2.geom)
                AND p1.den_uts != p2.den_uts
                ORDER BY p2.den_uts
            ''', [obj.pk])
            confinanti = cursor.fetchall()

        # Lista province confinanti
        if confinanti:
            lista_confinanti = ''.join([
                f'<span style="display: inline-flex; align-items: center; gap: 0.25rem; padding: 0.375rem 0.75rem; '
                f'background: #e0f2fe; color: #0369a1; border-radius: 9999px; font-size: 0.875rem; font-weight: 500;">'
                f'{nome} <span style="color: #0c4a6e; font-weight: 600;">({sigla})</span></span>'
                for nome, sigla in confinanti
            ])
            confinanti_html = f'''
                <div style="margin-bottom: 1rem;">
                    <div style="font-weight: 600; color: #374151; margin-bottom: 0.5rem;">Province confinanti ({len(confinanti)}):</div>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">{lista_confinanti}</div>
                </div>
            '''
        else:
            confinanti_html = '<div style="color: #6b7280; margin-bottom: 1rem;"><em>Nessuna provincia confinante trovata</em></div>'

        if geojson:
            return mark_safe(f'''
                {confinanti_html}
                <div id="map-{obj.pk}" style="height: 450px; width: 100%; border-radius: 8px; border: 1px solid #e5e7eb;"></div>
                <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
                <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
                <script>
                (function() {{
                    setTimeout(function() {{
                        var mapEl = document.getElementById("map-{obj.pk}");
                        if (!mapEl || mapEl._leaflet_id) return;

                        var map = L.map("map-{obj.pk}").setView([42.5, 12.5], 6);
                        L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
                            attribution: "&copy; OpenStreetMap"
                        }}).addTo(map);

                        var geojson = {geojson};
                        var layer = L.geoJSON(geojson, {{
                            style: {{
                                color: "#2563eb",
                                weight: 3,
                                fillColor: "#3b82f6",
                                fillOpacity: 0.2
                            }}
                        }}).addTo(map);

                        map.fitBounds(layer.getBounds(), {{ padding: [20, 20] }});
                    }}, 200);
                }})();
                </script>
            ''')
        return mark_safe(confinanti_html + "<em>Nessuna geometria disponibile</em>")
    map_preview.short_description = "Mappa Confini"



@admin.register(ScrapingCategoria)
class ScrapingCategoriaAdmin(ModelAdmin):
    list_display = ['categoria', 'count']
    search_fields = ['categoria']
    ordering = ['categoria']
    list_per_page = 50
    readonly_fields = ['categoria', 'count', 'eventi_list']

    fieldsets = (
        ('Informazioni', {
            'fields': ('categoria', 'count'),
        }),
        ('Eventi con questa categoria', {
            'fields': ('eventi_list',),
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def change_view(self, request, object_id, form_url='', extra_context=None):
        self._request = request
        return super().change_view(request, object_id, form_url, extra_context)

    def eventi_list(self, obj):
        from django.core.paginator import Paginator

        # Parametri dalla request
        request = getattr(self, '_request', None)
        page_num = 1
        city_filter = ''
        per_page = 25

        if request:
            page_num = int(request.GET.get('page', 1))
            city_filter = request.GET.get('city', '')

        # Query base
        queryset = StagingEvent.objects.filter(category__contains=[obj.categoria])

        # Ottieni lista città uniche per il filtro
        cities = queryset.values_list('city', flat=True).distinct().order_by('city')
        cities = [c for c in cities if c]

        # Applica filtro città
        if city_filter:
            queryset = queryset.filter(city=city_filter)

        # Paginazione
        paginator = Paginator(queryset, per_page)
        page = paginator.get_page(page_num)

        if page.object_list:
            rows = []
            for e in page.object_list:
                city = e.city or '-'
                rows.append(
                    f'<tr><td style="padding: 0.5rem; border-bottom: 1px solid #e5e7eb;">'
                    f'<a href="/admin/events/stagingevent/{e.pk}/change/" style="color: #2563eb; text-decoration: none;">{e.title}</a></td>'
                    f'<td style="padding: 0.5rem; border-bottom: 1px solid #e5e7eb;">{city}</td>'
                    f'<td style="padding: 0.5rem; border-bottom: 1px solid #e5e7eb;">{e.source}</td></tr>'
                )
            rows_html = ''.join(rows)

            # Dropdown città
            city_options = ''.join([
                f'<option value="{c}" {"selected" if c == city_filter else ""}>{c}</option>'
                for c in cities
            ])

            # Navigazione paginazione
            pagination_html = ''
            if paginator.num_pages > 1:
                base_url = f'?city={city_filter}' if city_filter else '?'
                prev_disabled = 'opacity: 0.5; pointer-events: none;' if not page.has_previous() else ''
                next_disabled = 'opacity: 0.5; pointer-events: none;' if not page.has_next() else ''

                # Genera link pagine
                page_links = []
                for p in paginator.page_range:
                    if p == page.number:
                        page_links.append(
                            f'<span style="padding: 0.25rem 0.5rem; background: #2563eb; color: white; border-radius: 4px; font-weight: 600;">{p}</span>'
                        )
                    elif abs(p - page.number) <= 2 or p == 1 or p == paginator.num_pages:
                        sep = '&' if city_filter else ''
                        page_links.append(
                            f'<a href="{base_url}{sep}page={p}" style="padding: 0.25rem 0.5rem; color: #2563eb; text-decoration: none;">{p}</a>'
                        )
                    elif abs(p - page.number) == 3:
                        page_links.append('<span style="padding: 0.25rem;">...</span>')

                prev_link = f'{base_url}{"&" if city_filter else ""}page={page.previous_page_number()}' if page.has_previous() else '#'
                next_link = f'{base_url}{"&" if city_filter else ""}page={page.next_page_number()}' if page.has_next() else '#'

                pagination_html = f'''
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #e5e7eb;">
                        <span style="color: #6b7280; font-size: 0.875rem;">
                            Mostrando {page.start_index()}-{page.end_index()} di {paginator.count} eventi
                        </span>
                        <div style="display: flex; align-items: center; gap: 0.5rem;">
                            <a href="{prev_link}" style="padding: 0.375rem 0.75rem; background: #f3f4f6; color: #374151; border-radius: 4px; text-decoration: none; {prev_disabled}">← Prec</a>
                            {''.join(page_links)}
                            <a href="{next_link}" style="padding: 0.375rem 0.75rem; background: #f3f4f6; color: #374151; border-radius: 4px; text-decoration: none; {next_disabled}">Succ →</a>
                        </div>
                    </div>
                '''

            return mark_safe(f'''
                <div style="margin-bottom: 1rem;">
                    <form method="get" style="display: flex; align-items: center; gap: 1rem;">
                        <label style="display: flex; align-items: center; gap: 0.5rem;">
                            <span style="font-weight: 500; color: #374151;">Filtra per città:</span>
                            <select name="city" onchange="this.form.submit()" style="padding: 0.375rem 0.75rem; border: 1px solid #d1d5db; border-radius: 4px; background: white;">
                                <option value="">Tutte le città</option>
                                {city_options}
                            </select>
                        </label>
                        {f'<a href="?" style="color: #dc2626; text-decoration: none; font-size: 0.875rem;">✕ Rimuovi filtro</a>' if city_filter else ''}
                    </form>
                </div>
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background: #f9fafb;">
                            <th style="padding: 0.5rem; text-align: left; border-bottom: 2px solid #e5e7eb;">Titolo</th>
                            <th style="padding: 0.5rem; text-align: left; border-bottom: 2px solid #e5e7eb;">Città</th>
                            <th style="padding: 0.5rem; text-align: left; border-bottom: 2px solid #e5e7eb;">Source</th>
                        </tr>
                    </thead>
                    <tbody>{rows_html}</tbody>
                </table>
                {pagination_html}
            ''')
        return "-"
    eventi_list.short_description = "Eventi"


@admin.register(ScrapingLocation)
class ScrapingLocationAdmin(ModelAdmin):
    list_display = ['nome_location_display', 'city', 'count']
    search_fields = ['location_name', 'city']
    list_filter = ['city']
    ordering = ['location_name']
    list_per_page = 50
    readonly_fields = ['nome_location_display', 'city', 'count', 'eventi_list']

    fieldsets = (
        ('Informazioni', {
            'fields': ('nome_location_display', 'city', 'count'),
        }),
        ('Eventi in questa location', {
            'fields': ('eventi_list',),
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def nome_location_display(self, obj):
        return obj.nome_location
    nome_location_display.short_description = "Location"

    def eventi_list(self, obj):
        nome = obj.nome_location
        eventi = StagingEvent.objects.filter(location_name=nome, city=obj.city)[:50]
        if eventi:
            rows = []
            for e in eventi:
                date_start = e.date_start or '-'
                rows.append(
                    f'<tr><td style="padding: 0.5rem; border-bottom: 1px solid #e5e7eb;">'
                    f'<a href="/admin/events/stagingevent/{e.pk}/change/" style="color: #2563eb; text-decoration: none;">{e.title}</a></td>'
                    f'<td style="padding: 0.5rem; border-bottom: 1px solid #e5e7eb;">{e.source}</td>'
                    f'<td style="padding: 0.5rem; border-bottom: 1px solid #e5e7eb;">{date_start}</td></tr>'
                )
            rows_html = ''.join(rows)
            return mark_safe(f'''
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background: #f9fafb;">
                            <th style="padding: 0.5rem; text-align: left; border-bottom: 2px solid #e5e7eb;">Titolo</th>
                            <th style="padding: 0.5rem; text-align: left; border-bottom: 2px solid #e5e7eb;">Source</th>
                            <th style="padding: 0.5rem; text-align: left; border-bottom: 2px solid #e5e7eb;">Data</th>
                        </tr>
                    </thead>
                    <tbody>{rows_html}</tbody>
                </table>
            ''')
        return "-"
    eventi_list.short_description = "Eventi"

