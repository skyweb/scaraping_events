import json
from django import forms
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin
from unfold.contrib.forms.widgets import WysiwygWidget
from unfold.contrib.filters.admin import RangeDateFilter
from .models import ProductionEvent, StagingEvent
from comuni_italiani.models import ComuneItaliano, ProvinciaItaliana
from comuni_italiani.admin import ProvinciaFilter, RegioneFilter
from scraping.admin import CategoriaFilter


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
                'SELECT ST_AsGeoJSON(ST_Transform(geom, 4326)) FROM comuni_italiani.comuni WHERE id = %s',
                [obj.pk]
            )
            row = cursor.fetchone()
            geojson = row[0] if row and row[0] else None

        # Query per ottenere il centroide
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT ST_AsGeoJSON(ST_Transform(centroid, 4326)) FROM comuni_italiani.comuni WHERE id = %s',
                [obj.pk]
            )
            row = cursor.fetchone()
            centroid = row[0] if row and row[0] else None

        # Query per ottenere i comuni confinanti con le loro geometrie
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT c2.comune, ST_AsGeoJSON(ST_Transform(c2.geom, 4326)), c2.id
                FROM comuni_italiani.comuni c1, comuni_italiani.comuni c2
                WHERE c1.id = %s
                AND ST_Touches(c1.geom, c2.geom)
                AND c1.id != c2.id
                ORDER BY c2.comune
            ''', [obj.pk])
            confinanti = cursor.fetchall()

        # Lista comuni confinanti con link
        if confinanti:
            lista_items = ''.join([
                f'<li style="margin-bottom: 0.5rem;">'
                f'<a href="/admin/comuni_italiani/comuneitaliano/{pk}/change/" '
                f'style="color: #2563eb; text-decoration: none; font-weight: 500;" '
                f'onmouseover="this.style.textDecoration=\'underline\'" '
                f'onmouseout="this.style.textDecoration=\'none\'">'
                f'{nome}</a></li>'
                for nome, geom, pk in confinanti
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
                {"nome": nome, "geom": json_lib.loads(geom)} for nome, geom, pk in confinanti if geom
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
                'SELECT ST_AsGeoJSON(ST_Transform(geom, 4326)) FROM comuni_italiani.province WHERE cod_uts = %s',
                [obj.pk]
            )
            row = cursor.fetchone()
            geojson = row[0] if row and row[0] else None

        # Query per ottenere le province confinanti
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT p2.den_uts, p2.sigla
                FROM comuni_italiani.province p1, comuni_italiani.province p2
                WHERE p1.cod_uts = %s
                AND ST_Touches(p1.geom, p2.geom)
                AND p1.cod_uts != p2.cod_uts
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

