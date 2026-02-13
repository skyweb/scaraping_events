from django import forms
from django.contrib import admin
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin, TabularInline, StackedInline

from .models import (
    PaginaCitta, TabNavigazione, SezionePagina, ArticoloSezione,
    EventoInSezione, SezioneEventi, EventoSelezionato,
)
from .widgets import ImagePopupWidget


# =============================================================================
# Inline
# =============================================================================

class TabNavigazioneInline(TabularInline):
    model = TabNavigazione
    extra = 1
    min_num = 1
    fields = ['label', 'url', 'ordine']


class SezionePaginaInline(TabularInline):
    model = SezionePagina
    extra = 0
    fields = ['titolo_link', 'ordine', 'stato_chip']
    readonly_fields = ['titolo_link', 'stato_chip']
    can_delete = False

    def titolo_link(self, obj):
        if not obj.pk:
            return '-'
        url = f'/admin/cms/sezionepagina/{obj.pk}/change/'
        return mark_safe(f'<a href="{url}" style="font-weight:600;">{obj.titolo}</a>')
    titolo_link.short_description = 'Titolo'

    def stato_chip(self, obj):
        if not obj.pk:
            return '-'
        if obj.is_attiva:
            color, bg, label = '#065f46', '#d1fae5', 'Attivo'
        else:
            color, bg, label = '#991b1b', '#fee2e2', 'Disattivo'
        return mark_safe(
            f'<span style="display:inline-block;padding:2px 10px;border-radius:9999px;'
            f'font-size:.75rem;font-weight:600;color:{color};background:{bg};">'
            f'{label}</span>'
        )
    stato_chip.short_description = 'Stato'

    def has_add_permission(self, request, obj=None):
        return False


class ArticoloSezioneInline(StackedInline):
    model = ArticoloSezione
    extra = 1
    fields = [('titolo', 'url'), ('immagine_url', 'immagine_preview'), ('categoria', 'colore_categoria', 'ordine')]
    readonly_fields = ['immagine_preview']

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name in ('titolo', 'url'):
            kwargs['widget'] = forms.TextInput(attrs={'style': 'width:100%'})
        if db_field.name == 'immagine_url':
            kwargs['widget'] = forms.URLInput(attrs={'style': 'width:100%'})
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def immagine_preview(self, obj):
        url = obj.immagine_finale if obj.pk else ''
        if not url:
            return '-'
        return mark_safe(
            f'<img src="{url}" style="height:50px;border-radius:4px;object-fit:cover;">'
        )
    immagine_preview.short_description = 'Anteprima'


class EventoInSezioneInline(TabularInline):
    """Inline per selezionare staging events dentro una SezionePagina."""
    model = EventoInSezione
    extra = 1
    autocomplete_fields = ['evento']
    readonly_fields = ['evento_preview']
    fields = ['evento', 'evento_preview', 'ordine']

    def evento_preview(self, obj):
        if not obj.pk or not obj.evento_id:
            return '-'
        ev = obj.evento
        img = ''
        if ev.image_url:
            img = (
                f'<img src="{ev.image_url}" '
                f'style="width:60px;height:40px;object-fit:cover;border-radius:4px;vertical-align:middle;margin-right:8px;">'
            )
        cat = ev.category[0] if ev.category else ''
        title = ev.title[:50] + ('...' if len(ev.title) > 50 else '')
        return mark_safe(
            f'{img}'
            f'<span style="color:#6b7280;font-size:.75rem;">{cat}</span> '
            f'<strong>{title}</strong>'
        )
    evento_preview.short_description = 'Anteprima'


class EventoSelezionatoInline(TabularInline):
    model = EventoSelezionato
    extra = 1
    autocomplete_fields = ['evento']
    readonly_fields = ['evento_preview']
    fields = ['evento', 'evento_preview', 'ordine']

    def evento_preview(self, obj):
        """Anteprima: thumbnail + categoria + titolo troncato."""
        if not obj.pk or not obj.evento_id:
            return '-'
        ev = obj.evento
        img = ''
        if ev.image_url:
            img = (
                f'<img src="{ev.image_url}" '
                f'style="width:60px;height:40px;object-fit:cover;border-radius:4px;vertical-align:middle;margin-right:8px;">'
            )
        cat = ev.category[0] if ev.category else ''
        title = ev.title[:50] + ('...' if len(ev.title) > 50 else '')
        return mark_safe(
            f'{img}'
            f'<span style="color:#6b7280;font-size:.75rem;">{cat}</span> '
            f'<strong>{title}</strong>'
        )
    evento_preview.short_description = 'Anteprima'


class SezioneEventiInline(StackedInline):
    model = SezioneEventi
    extra = 0
    fields = ['titolo', 'colore', 'link_vedi_tutti', 'ordine', 'is_attiva']
    show_change_link = True


# =============================================================================
# PaginaCitta Admin
# =============================================================================

@admin.register(PaginaCitta)
class PaginaCittaAdmin(ModelAdmin):
    """Admin pagina città con tab Unfold: Città, Navigazione, Sezioni."""
    list_display = ['nome', 'slug', 'is_attiva', 'ordine', 'updated_at']
    list_filter = ['is_attiva']
    search_fields = ['nome', 'slug']
    prepopulated_fields = {'slug': ('nome',)}
    readonly_fields = ['created_at', 'updated_at']
    inlines = [TabNavigazioneInline, SezionePaginaInline]

    fieldsets = (
        (None, {
            'fields': ('nome', 'slug', 'is_attiva', 'ordine', 'created_at', 'updated_at'),
        }),
    )


# =============================================================================
# SezionePagina Admin
# =============================================================================

@admin.register(SezionePagina)
class SezionePaginaAdmin(ModelAdmin):
    """Admin sezione pagina con tab Unfold: Sezione, Articoli."""
    list_display = ['titolo', 'pagina', 'colore_chip', 'ordine', 'stato_chip']
    list_filter = ['is_attiva', 'colore', 'pagina']
    search_fields = ['titolo', 'pagina__nome']
    inlines = [ArticoloSezioneInline, EventoInSezioneInline]

    fieldsets = (
        (mark_safe('<span style="display:inline-flex;align-items:center;gap:.5rem;">'
                    '<span class="material-symbols-outlined">dashboard</span> Sezione</span>'), {
            'fields': ('pagina', 'titolo', ('colore', 'link_vedi_tutti', 'ordine'), 'is_attiva'),
            'classes': ['tab'],
        }),
        (mark_safe('<span style="display:inline-flex;align-items:center;gap:.5rem;">'
                    '<span class="material-symbols-outlined">article</span> Articoli</span>'), {
            'fields': [],
            'classes': ['tab'],
            'description': 'Gestisci le card/articoli manuali di questa sezione.',
        }),
        (mark_safe('<span style="display:inline-flex;align-items:center;gap:.5rem;">'
                    '<span class="material-symbols-outlined">event</span> Eventi</span>'), {
            'fields': [],
            'classes': ['tab'],
            'description': 'Seleziona staging events da mostrare come articoli.',
        }),
    )

    COLORE_MAP = {
        'blue': ('#1e40af', '#dbeafe'),
        'green': ('#065f46', '#d1fae5'),
        'red': ('#991b1b', '#fee2e2'),
        'orange': ('#92400e', '#fef3c7'),
        'yellow': ('#713f12', '#fef9c3'),
        'purple': ('#581c87', '#f3e8ff'),
    }

    def colore_chip(self, obj):
        """Chip colorato per il colore della sezione."""
        color, bg = self.COLORE_MAP.get(obj.colore, ('#6b7280', '#f3f4f6'))
        return mark_safe(
            f'<span style="display:inline-block;padding:2px 10px;border-radius:9999px;'
            f'font-size:.75rem;font-weight:600;color:{color};background:{bg};">'
            f'{obj.get_colore_display()}</span>'
        )
    colore_chip.short_description = 'Colore'

    def stato_chip(self, obj):
        if obj.is_attiva:
            color, bg, label = '#065f46', '#d1fae5', 'Attivo'
        else:
            color, bg, label = '#991b1b', '#fee2e2', 'Disattivo'
        return mark_safe(
            f'<span style="display:inline-block;padding:2px 10px;border-radius:9999px;'
            f'font-size:.75rem;font-weight:600;color:{color};background:{bg};">'
            f'{label}</span>'
        )
    stato_chip.short_description = 'Stato'


# =============================================================================
# SezioneEventi Admin
# =============================================================================

@admin.register(SezioneEventi)
class SezioneEventiAdmin(ModelAdmin):
    """Admin sezione eventi — nascosto dall'indice, accessibile via change link."""

    def get_model_perms(self, request):
        """Nasconde il modello dall'indice /admin/cms/."""
        return {}
    list_display = ['titolo', 'pagina', 'colore_chip', 'conteggio_eventi', 'ordine', 'is_attiva']
    list_filter = ['is_attiva', 'colore', 'pagina']
    search_fields = ['titolo', 'pagina__nome']
    inlines = [EventoSelezionatoInline]

    fieldsets = (
        (mark_safe('<span style="display:inline-flex;align-items:center;gap:.5rem;">'
                    '<span class="material-symbols-outlined">dashboard</span> Sezione</span>'), {
            'fields': ('pagina', 'titolo', 'colore', 'link_vedi_tutti', 'ordine', 'is_attiva'),
            'classes': ['tab'],
        }),
        (mark_safe('<span style="display:inline-flex;align-items:center;gap:.5rem;">'
                    '<span class="material-symbols-outlined">event</span> Eventi</span>'), {
            'fields': [],
            'classes': ['tab'],
            'description': 'Seleziona gli staging events da mostrare in questa sezione.',
        }),
    )

    COLORE_MAP = SezionePaginaAdmin.COLORE_MAP

    def colore_chip(self, obj):
        color, bg = self.COLORE_MAP.get(obj.colore, ('#6b7280', '#f3f4f6'))
        return mark_safe(
            f'<span style="display:inline-block;padding:2px 10px;border-radius:9999px;'
            f'font-size:.75rem;font-weight:600;color:{color};background:{bg};">'
            f'{obj.get_colore_display()}</span>'
        )
    colore_chip.short_description = 'Colore'

    def conteggio_eventi(self, obj):
        return obj.eventi.count()
    conteggio_eventi.short_description = 'Eventi'
