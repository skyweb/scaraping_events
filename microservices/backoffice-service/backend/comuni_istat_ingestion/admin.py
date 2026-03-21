from urllib.parse import quote

from django.contrib import admin
from django.db.models import Count
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin, TabularInline

from .models import (
    Regione, Provincia, Comune,
    Appartenenza, ComuneFrazione, ComuneConfinante, ComuneAppartenenza,
    ComunePuntoInteresse, ComuneEvento, ComuneGemellaggio,
    ComuneCittadinoIllustre,
)


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
        """Link al dettaglio dell'appartenenza normalizzata con elenco comuni."""
        if not obj.pk or not obj.appartenenza_id:
            return '-'
        url = f'/admin/comuni_istat_ingestion/appartenenza/{obj.appartenenza_id}/change/'
        return mark_safe(
            f'<a href="{url}" style="white-space:nowrap;" title="Vedi tutti i comuni con questa appartenenza">'
            f'Vedi comuni &rarr;</a>'
        )
    cerca_comuni.short_description = 'Dettaglio'


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
# Appartenenze normalizzate
# =============================================================================

class AppartenenzaComuneInline(TabularInline):
    """Inline readonly: mostra i comuni che appartengono a questa entità."""
    model = ComuneAppartenenza
    fk_name = 'appartenenza'
    fields = ['comune_link', 'codice_istat_link', 'provincia_display', 'regione_display']
    readonly_fields = fields
    extra = 0
    can_delete = False
    verbose_name_plural = mark_safe('Appartenenze')

    def get_formset(self, request, obj=None, **kwargs):
        """Aggiunge chip con conteggio comuni nel titolo dell'inline."""
        formset = super().get_formset(request, obj, **kwargs)
        if obj:
            count = ComuneAppartenenza.objects.filter(appartenenza=obj).count()
            chip = (
                f'<span style="background:#f59e0b;color:#fff;font-size:12px;font-weight:700;'
                f'padding:2px 9px;border-radius:12px;margin-left:8px;vertical-align:middle;">'
                f'{count}</span>'
            )
            self.verbose_name_plural = mark_safe(f'Appartenenze {chip}')
        return formset

    def has_add_permission(self, request, obj=None):
        """Disabilita l'aggiunta manuale: le appartenenze sono importate dallo scraping."""
        return False

    def comune_link(self, obj):
        """Mostra il nome del comune come link alla scheda di dettaglio."""
        url = f'/admin/comuni_istat_ingestion/comune/{obj.comune_id}/change/'
        return mark_safe(f'<a href="{url}">{obj.comune.nome}</a>')
    comune_link.short_description = 'Comune'

    def codice_istat_link(self, obj):
        """Mostra il codice ISTAT con link alla scheda ISTAT del comune, se collegato."""
        codice = obj.comune.codice_istat or obj.comune.codice_catastale or '-'
        comune_istat = getattr(obj.comune, 'comune_istat', None)
        if not comune_istat:
            return codice
        url = f'/admin/comuni_istat/comuneitaliano/{comune_istat.pk}/change/'
        return mark_safe(
            f'<a href="{url}" style="color:#7c3aed;font-weight:600;text-decoration:none;">'
            f'{codice} '
            f'<span class="material-symbols-outlined" style="font-size:.9rem;vertical-align:middle;">open_in_new</span></a>'
        )
    codice_istat_link.short_description = 'Cod. ISTAT'

    def provincia_display(self, obj):
        """Mostra il nome della provincia del comune."""
        return obj.comune.provincia.nome
    provincia_display.short_description = 'Provincia'

    def regione_display(self, obj):
        """Mostra il nome della regione del comune."""
        return obj.comune.provincia.regione.nome
    regione_display.short_description = 'Regione'

    def get_queryset(self, request):
        """Ottimizza il queryset con select_related su provincia, regione e comune ISTAT."""
        return super().get_queryset(request).select_related('comune__provincia__regione', 'comune__comune_istat')


@admin.register(Appartenenza)
class AppartenenzaAdmin(ModelAdmin):
    """Entità di appartenenza normalizzata con elenco comuni membri."""
    list_display = ['nome', 'num_comuni']
    search_fields = ['nome']
    list_per_page = 50
    inlines = [AppartenenzaComuneInline]

    def get_queryset(self, request):
        """Aggiunge l'annotazione con il conteggio dei comuni appartenenti."""
        return super().get_queryset(request).annotate(_num_comuni=Count('comuni_appartenenza'))

    @admin.display(description='Comuni', ordering='_num_comuni')
    def num_comuni(self, obj) -> int:
        """Mostra il numero di comuni associati a questa appartenenza."""
        return obj._num_comuni


@admin.register(ComuneAppartenenza)
class ComuneAppartenenzaAdmin(ModelAdmin):
    """Cerca un'appartenenza per trovare tutti i comuni che la condividono."""
    list_display = ['nome', 'comune_link', 'provincia_display', 'regione_display']
    search_fields = ['nome']
    list_filter = ['comune__provincia__regione']
    list_per_page = 50
    list_select_related = ['comune__provincia__regione']

    def comune_link(self, obj):
        """Mostra il nome del comune come link alla scheda di dettaglio."""
        url = f'/admin/comuni_istat_ingestion/comune/{obj.comune_id}/change/'
        return mark_safe(f'<a href="{url}">{obj.comune.nome}</a>')
    comune_link.short_description = 'Comune'
    comune_link.admin_order_field = 'comune__nome'

    def provincia_display(self, obj):
        """Mostra il nome della provincia del comune."""
        return obj.comune.provincia.nome
    provincia_display.short_description = 'Provincia'
    provincia_display.admin_order_field = 'comune__provincia__nome'

    def regione_display(self, obj):
        """Mostra il nome della regione del comune."""
        return obj.comune.provincia.regione.nome
    regione_display.short_description = 'Regione'
    regione_display.admin_order_field = 'comune__provincia__regione__nome'
