from urllib.parse import quote

from django.contrib import admin
from django.db.models import Count
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin, TabularInline

from .models import (
    ComuniIstatRawData,
    Regione, Provincia, Comune,
    ComuneFrazione, ComuneConfinante, ComuneAppartenenza,
    ComunePuntoInteresse, ComuneEvento, ComuneGemellaggio,
    ComuneCittadinoIllustre,
)


# =============================================================================
# Raw Data
# =============================================================================

@admin.register(ComuniIstatRawData)
class ComuniIstatRawDataAdmin(ModelAdmin):
    list_display = ['tipo', 'codice_istat', 'regione', 'provincia', 'comune', 'created_at']
    list_filter = ['tipo']
    search_fields = ['codice_istat', 'regione', 'provincia', 'comune']
    readonly_fields = ['created_at', 'raw_json']
    list_per_page = 50


# =============================================================================
# Inline per il dettaglio Comune
# =============================================================================

class FrazioneInline(TabularInline):
    model = ComuneFrazione
    extra = 0
    fields = ['nome', 'ordine']


class ConfinanteInline(TabularInline):
    model = ComuneConfinante
    extra = 0
    fields = ['descrizione', 'ordine']


class AppartenenzaInline(TabularInline):
    model = ComuneAppartenenza
    extra = 0
    fields = ['nome', 'cerca_comuni', 'ordine']
    readonly_fields = ['cerca_comuni']

    def cerca_comuni(self, obj):
        """Link per cercare tutti i comuni con la stessa appartenenza."""
        if not obj.pk:
            return '-'
        url = f'/admin/comuni_istat_ingestion/comuneappartenenza/?q={quote(obj.nome)}'
        return mark_safe(
            f'<a href="{url}" style="white-space:nowrap;" title="Cerca tutti i comuni con questa appartenenza">'
            f'Cerca comuni &rarr;</a>'
        )
    cerca_comuni.short_description = 'Filtra'


class PuntoInteresseInline(TabularInline):
    model = ComunePuntoInteresse
    extra = 0
    fields = ['tipo', 'nome', 'ordine']


class EventoInline(TabularInline):
    model = ComuneEvento
    extra = 0
    fields = ['nome', 'ordine']


class GemellaggioInline(TabularInline):
    model = ComuneGemellaggio
    extra = 0
    fields = ['citta', 'ordine']


class CittadinoIllustreInline(TabularInline):
    model = ComuneCittadinoIllustre
    extra = 0
    fields = ['nome', 'ordine']


# =============================================================================
# Admin principali
# =============================================================================

@admin.register(Regione)
class RegioneAdmin(ModelAdmin):
    list_display = ['nome', 'codice_istat', 'capoluogo', 'popolazione', 'num_province', 'num_comuni']
    search_fields = ['nome', 'codice_istat']
    list_per_page = 25


@admin.register(Provincia)
class ProvinciaAdmin(ModelAdmin):
    list_display = ['nome', 'sigla', 'codice_istat', 'regione', 'capoluogo', 'popolazione', 'num_comuni']
    search_fields = ['nome', 'sigla', 'codice_istat']
    list_filter = ['regione']
    list_per_page = 50


@admin.register(Comune)
class ComuneAdmin(ModelAdmin):
    list_display = ['nome', 'codice_istat', 'provincia', 'cap', 'popolazione']
    search_fields = ['nome', 'codice_istat', 'codice_catastale', 'cap']
    list_filter = ['provincia__regione']
    list_per_page = 50
    inlines = [
        FrazioneInline,
        ConfinanteInline,
        AppartenenzaInline,
        PuntoInteresseInline,
        EventoInline,
        GemellaggioInline,
        CittadinoIllustreInline,
    ]

    fieldsets = (
        (None, {
            'fields': (
                ('nome', 'codice_istat', 'codice_catastale'),
                ('provincia', 'zona', 'cap', 'prefisso_telefonico'),
                ('popolazione', 'superficie_kmq', 'densita'),
                ('patrono', 'festa_patronale'),
                ('demonimo', 'etimologia'),
                'il_comune_e',
            ),
        }),
    )


# =============================================================================
# Appartenenze (admin dedicato con ricerca)
# =============================================================================

@admin.register(ComuneAppartenenza)
class ComuneAppartenenzaAdmin(ModelAdmin):
    """Cerca un'appartenenza per trovare tutti i comuni che la condividono."""
    list_display = ['nome', 'comune_link', 'provincia_display', 'regione_display']
    search_fields = ['nome']
    list_filter = ['comune__provincia__regione']
    list_per_page = 50
    list_select_related = ['comune__provincia__regione']

    def comune_link(self, obj):
        url = f'/admin/comuni_istat_ingestion/comune/{obj.comune_id}/change/'
        return mark_safe(f'<a href="{url}">{obj.comune.nome}</a>')
    comune_link.short_description = 'Comune'
    comune_link.admin_order_field = 'comune__nome'

    def provincia_display(self, obj):
        return obj.comune.provincia.nome
    provincia_display.short_description = 'Provincia'
    provincia_display.admin_order_field = 'comune__provincia__nome'

    def regione_display(self, obj):
        return obj.comune.provincia.regione.nome
    regione_display.short_description = 'Regione'
    regione_display.admin_order_field = 'comune__provincia__regione__nome'
