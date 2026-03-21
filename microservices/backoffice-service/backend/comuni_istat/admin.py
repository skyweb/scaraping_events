from urllib.parse import quote

from django.contrib import admin
from django.db import connection
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin, TabularInline


def _bool_chip(value: bool | None, label_true: str = "Sì", label_false: str = "No") -> str:
    """Chip verde/rosso per valori booleani."""
    if value is None:
        return "-"
    if value:
        return format_html(
            '<span style="display:inline-block;padding:2px 10px;border-radius:9999px;'
            'font-size:.75rem;font-weight:600;color:#065f46;background:#d1fae5;">{}</span>',
            label_true,
        )
    return format_html(
        '<span style="display:inline-block;padding:2px 10px;border-radius:9999px;'
        'font-size:.75rem;font-weight:600;color:#991b1b;background:#fee2e2;">{}</span>',
        label_false,
    )

from .models import (
    RipartizioneGeografica,
    Regione,
    Provincia,
    Comune,
    ComuneSoppresso,
    DenominazionePrecedente,
)
from comuni_italiani.models import (
    Comune as ComuneIngestion,
    ComuneAppartenenza,
)


class RegioneFilter(admin.SimpleListFilter):
    """Filtro per regione nei comuni"""
    title = 'Regione'
    parameter_name = 'regione'

    def lookups(self, request, model_admin):
        """Restituisce l'elenco delle regioni (cod_reg, den_reg) per il menu a tendina."""
        with connection.cursor() as cursor:
            cursor.execute('SELECT cod_reg, den_reg FROM comuni_istat.regioni ORDER BY den_reg')
            return cursor.fetchall()

    def queryset(self, request, queryset):
        """Filtra il queryset per codice regione selezionata."""
        if self.value():
            return queryset.filter(cod_reg=self.value())
        return queryset


class ProvinciaFilter(admin.SimpleListFilter):
    """Filtro per provincia nei comuni"""
    title = 'Provincia'
    parameter_name = 'provincia'

    def lookups(self, request, model_admin):
        """Restituisce l'elenco delle province (cod_uts, den_uts) per il menu a tendina."""
        with connection.cursor() as cursor:
            cursor.execute('SELECT cod_uts, den_uts FROM comuni_istat.province ORDER BY den_uts')
            return cursor.fetchall()

    def queryset(self, request, queryset):
        """Filtra il queryset per codice UTS della provincia selezionata."""
        if self.value():
            return queryset.filter(cod_uts_id=self.value())
        return queryset


class DenominazionePrecedenteInline(TabularInline):
    model = DenominazionePrecedente
    fk_name = 'comune_attuale'
    fields = ['comune', 'sigla_uts', 'cod_den_storico']
    readonly_fields = fields
    extra = 0
    can_delete = False
    verbose_name = 'Denominazione storica'
    verbose_name_plural = 'guardaDenominazioni storiche'

    def has_add_permission(self, request, obj=None):
        """Disabilita l'aggiunta manuale: le denominazioni storiche sono importate da fixture."""
        return False


class ComuneSoppressoInline(TabularInline):
    model = ComuneSoppresso
    fk_name = 'comune_attuale'
    fields = ['comune', 'sigla_uts', 'anno', 'cod_variazione', 'data_inizio', 'pro_com_t']
    readonly_fields = fields
    extra = 0
    can_delete = False
    verbose_name = 'Denominazione precedente'
    verbose_name_plural = 'Denominazioni precedenti (comuni soppressi)'

    def has_add_permission(self, request, obj=None):
        """Disabilita l'aggiunta manuale: i comuni soppressi sono importati da fixture."""
        return False


@admin.register(Comune)
class ComuneAdmin(ModelAdmin):
    list_display = ['comune', 'cod_uts', 'popolazione', 'attivo']
    search_fields = ['comune', 'comuni_soppressi__comune', 'denominazioni_precedenti__comune']
    list_filter = ['attivo', RegioneFilter, ProvinciaFilter]
    list_per_page = 50
    exclude = ['geom', 'centroid', 'shape_area', 'shape_length']

    _custom_display_fields = [
        'mappa_confini', 'zona_altimetrica_display', 'grado_urbanizzazione_display',
        'attivo_chip', 'litoraneo_chip', 'isolano_chip', 'link_ingestion',
        'appartenenze_display',
    ]

    def get_readonly_fields(self, request, obj=None):
        """Tutti i campi sono readonly — dati importati da fixture."""
        if obj:
            fields = [f.name for f in obj._meta.get_fields() if hasattr(f, 'column') and f.name not in self.exclude]
            return fields + self._custom_display_fields
        return list(self._custom_display_fields)
    inlines = [DenominazionePrecedenteInline, ComuneSoppressoInline]

    fieldsets = (
        (mark_safe('<span style="display:inline-flex;align-items:center;gap:.5rem;">'
                   '<span class="material-symbols-outlined">location_city</span> Anagrafica</span>'), {
            'fields': (
                ('comune', 'comune_a', 'cod_uts'),
                ('pro_com', 'pro_com_t', 'link_ingestion'),
                ('cod_rip', 'cod_reg', 'cod_prov'),
                ('cap', 'popolazione', 'attivo_chip'),
            ),
            'classes': ['tab'],
        }),
        (mark_safe('<span style="display:inline-flex;align-items:center;gap:.5rem;">'
                   '<span class="material-symbols-outlined">terrain</span> Caratteristiche</span>'), {
            'fields': (
                ('altitudine', 'zona_altimetrica_display', 'grado_urbanizzazione_display'),
                ('litoraneo_chip', 'isolano_chip', 'zona_costiera'),
                ('ecoregione_divisione', 'ecoregione_provincia', 'ecoregione_sezione'),
                ('ecoregione_sottosezione',),
            ),
            'classes': ['tab'],
        }),
        (mark_safe('<span style="display:inline-flex;align-items:center;gap:.5rem;">'
                   '<span class="material-symbols-outlined">map</span> Mappa confini</span>'), {
            'fields': ('mappa_confini',),
            'classes': ['tab'],
        }),
        (mark_safe('<span style="display:inline-flex;align-items:center;gap:.5rem;">'
                   '<span class="material-symbols-outlined">groups</span> Appartenenze</span>'), {
            'fields': ('appartenenze_display',),
        }),
    )

    ZONA_ALTIMETRICA_MAP = {
        1: "Montagna interna",
        2: "Montagna litoranea",
        3: "Collina interna",
        4: "Collina litoranea",
        5: "Pianura",
    }

    GRADO_URBANIZZAZIONE_MAP = {
        1: "Densamente popolato",
        2: "Mediamente popolato",
        3: "Scarsamente popolato",
    }

    @admin.display(description="Zona altimetrica")
    def zona_altimetrica_display(self, obj) -> str:
        """Mostra il codice e la descrizione della zona altimetrica ISTAT."""
        if obj.zona_altimetrica is None:
            return "-"
        label = self.ZONA_ALTIMETRICA_MAP.get(obj.zona_altimetrica, "Sconosciuta")
        return f"{obj.zona_altimetrica} — {label}"

    @admin.display(description="Grado urbanizzazione")
    def grado_urbanizzazione_display(self, obj) -> str:
        """Mostra il codice e la descrizione del grado di urbanizzazione DEGURBA."""
        if obj.grado_urbanizzazione is None:
            return "-"
        label = self.GRADO_URBANIZZAZIONE_MAP.get(obj.grado_urbanizzazione, "Sconosciuto")
        return f"{obj.grado_urbanizzazione} — {label}"

    @admin.display(description="Codice catastale")
    def link_ingestion(self, obj) -> str:
        """Mostra il codice catastale con link alla scheda ingestion del comune, se collegato."""
        if not obj.codice_catastale:
            return "-"
        if not obj.comune_ingestion_id:
            return obj.codice_catastale
        url = f'/admin/comuni_italiani/comune/{obj.comune_ingestion_id}/change/'
        return format_html(
            '<a href="{}" style="color:#7c3aed;font-weight:600;text-decoration:none;">{} '
            '<span class="material-symbols-outlined" style="font-size:.9rem;vertical-align:middle;">open_in_new</span></a>',
            url, obj.codice_catastale,
        )

    @admin.display(description="Attivo")
    def attivo_chip(self, obj) -> str:
        """Mostra un chip colorato verde/rosso per lo stato attivo del comune."""
        return _bool_chip(obj.attivo, "Attivo", "Non attivo")

    @admin.display(description="Litoraneo")
    def litoraneo_chip(self, obj) -> str:
        """Mostra un chip colorato verde/rosso per indicare se il comune è litoraneo."""
        return _bool_chip(obj.comune_litoraneo, "Litoraneo", "Non litoraneo")

    @admin.display(description="Isolano")
    def isolano_chip(self, obj) -> str:
        """Mostra un chip colorato verde/rosso per indicare se il comune è isolano."""
        return _bool_chip(obj.comune_isolano, "Isolano", "Non isolano")

    @admin.display(description="Appartenenze")
    def appartenenze_display(self, obj) -> str:
        """Elenco appartenenze come tabella inline readonly."""
        if not obj.comune_ingestion_id:
            return "-"
        appartenenze = (
            ComuneAppartenenza.objects
            .filter(comune_id=obj.comune_ingestion_id)
            .select_related('appartenenza')
        )
        if not appartenenze:
            return "-"
        rows = []
        for ca in appartenenze:
            if ca.appartenenza_id:
                url = f'/admin/comuni_italiani/appartenenza/{ca.appartenenza_id}/change/'
                nome_html = format_html(
                    '<a href="{}" style="color:#7c3aed;text-decoration:none;">{}</a>',
                    url, ca.nome,
                )
            else:
                nome_html = ca.nome
            rows.append(f'<tr><td style="padding:8px 12px;border-bottom:1px solid '
                        f'var(--border-color, #e5e7eb);">{nome_html}</td></tr>')
        return mark_safe(
            '<table style="width:100%;border-collapse:collapse;">'
            '<thead><tr><th style="padding:8px 12px;text-align:left;font-weight:600;'
            'font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;'
            'color:var(--text-secondary-color, #6b7280);border-bottom:2px solid '
            'var(--border-color, #e5e7eb);">Nome</th></tr></thead>'
            '<tbody>' + ''.join(rows) + '</tbody></table>'
        )

    class Media:
        js = ['comuni_istat/js/mappa_confini.js', 'comuni_istat/js/appartenenze_bottom.js']

    def mappa_confini(self, obj):
        """Mappa Leaflet con confini del comune e centroide."""
        if not obj.geom:
            return "Geometria non disponibile"

        geojson = obj.geom.geojson
        centroid_lat = obj.centroid.y if obj.centroid else obj.geom.centroid.y
        centroid_lng = obj.centroid.x if obj.centroid else obj.geom.centroid.x

        return mark_safe(
            f'<div id="map-comune" style="height:70vh;width:100%;border-radius:8px;margin-top:8px;"'
            f' data-geojson=\'{geojson}\''
            f' data-lat="{centroid_lat}"'
            f' data-lng="{centroid_lng}"></div>'
        )

    mappa_confini.short_description = "Mappa confini"


@admin.register(Provincia)
class ProvinciaAdmin(ModelAdmin):
    list_display = ['den_uts', 'sigla', 'cod_reg']
    search_fields = ['den_uts', 'sigla']
    list_filter = [RegioneFilter]
    list_per_page = 50
    exclude = ['geom', 'shape_area', 'shape_length']

    _custom_display_fields = ['link_ingestion']

    fieldsets = (
        (None, {
            'fields': (
                ('den_uts', 'link_ingestion'),
                ('den_prov', 'den_cm'),
                ('cod_uts', 'cod_prov'),
                ('cod_rip', 'cod_reg'),
                ('cod_cm', 'tipo_uts'),
            ),
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        """Tutti i campi sono readonly — dati importati da fixture."""
        if obj:
            fields = [f.name for f in obj._meta.get_fields() if hasattr(f, 'column') and f.name not in self.exclude]
            return fields + self._custom_display_fields
        return list(self._custom_display_fields)

    @admin.display(description="Sigla")
    def link_ingestion(self, obj) -> str:
        """Mostra la sigla della provincia con link alla scheda ingestion, se collegata."""
        if not obj.sigla:
            return "-"
        if not obj.provincia_ingestion_id:
            return obj.sigla
        url = f'/admin/comuni_italiani/provincia/{obj.provincia_ingestion_id}/change/'
        return format_html(
            '<a href="{}" style="color:#7c3aed;font-weight:600;text-decoration:none;">{} '
            '<span class="material-symbols-outlined" style="font-size:.9rem;vertical-align:middle;">open_in_new</span></a>',
            url, obj.sigla,
        )
