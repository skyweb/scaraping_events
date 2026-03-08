from django.contrib import admin
from django.db import connection
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin

from unfold.admin import TabularInline

from .models import (
    RipartizioneGeografica,
    RegioneItaliana,
    ProvinciaItaliana,
    ComuneItaliano,
    ComuneSoppresso,
    DenominazionePrecedente,
)


class RegioneFilter(admin.SimpleListFilter):
    """Filtro per regione nei comuni"""
    title = 'Regione'
    parameter_name = 'regione'

    def lookups(self, request, model_admin):
        with connection.cursor() as cursor:
            cursor.execute('SELECT cod_reg, den_reg FROM comuni_istat.regioni ORDER BY den_reg')
            return cursor.fetchall()

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(cod_reg=self.value())
        return queryset


class ProvinciaFilter(admin.SimpleListFilter):
    """Filtro per provincia nei comuni"""
    title = 'Provincia'
    parameter_name = 'provincia'

    def lookups(self, request, model_admin):
        with connection.cursor() as cursor:
            cursor.execute('SELECT cod_uts, den_uts FROM comuni_istat.province ORDER BY den_uts')
            return cursor.fetchall()

    def queryset(self, request, queryset):
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
    verbose_name_plural = 'Denominazioni storiche'

    def has_add_permission(self, request, obj=None):
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
        return False


@admin.register(ComuneItaliano)
class ComuneItalianoAdmin(ModelAdmin):
    list_display = ['comune', 'cod_uts', 'popolazione', 'attivo']
    search_fields = ['comune', 'comuni_soppressi__comune', 'denominazioni_precedenti__comune']
    list_filter = ['attivo', RegioneFilter, ProvinciaFilter]
    list_per_page = 50
    exclude = ['geom', 'centroid', 'shape_area', 'shape_length']
    readonly_fields = ['mappa_confini']
    inlines = [DenominazionePrecedenteInline, ComuneSoppressoInline]

    class Media:
        js = ['comuni_istat/js/mappa_confini.js']

    def mappa_confini(self, obj):
        """Mappa Leaflet con confini del comune e centroide."""
        if not obj.geom:
            return "Geometria non disponibile"

        geojson = obj.geom.geojson
        centroid_lat = obj.centroid.y if obj.centroid else obj.geom.centroid.y
        centroid_lng = obj.centroid.x if obj.centroid else obj.geom.centroid.x

        return mark_safe(
            f'<div id="map-comune" style="height:450px;width:100%;border-radius:8px;margin-top:8px;"'
            f' data-geojson=\'{geojson}\''
            f' data-lat="{centroid_lat}"'
            f' data-lng="{centroid_lng}"></div>'
        )

    mappa_confini.short_description = "Mappa confini"


@admin.register(ProvinciaItaliana)
class ProvinciaItalianaAdmin(ModelAdmin):
    list_display = ['den_uts', 'sigla', 'cod_reg']
    search_fields = ['den_uts', 'sigla']
    list_filter = [RegioneFilter]
    list_per_page = 50
    exclude = ['geom', 'shape_area', 'shape_length']
