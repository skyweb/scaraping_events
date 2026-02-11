"""
Configurazione admin per i modelli di scraping (categorie e location aggregate).
"""
from django.contrib import admin
from django.db import connection
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin

from .models import ScrapingCategory, ScrapingLocation
from events.admin_utils import format_date_italian, format_datetime_italian, render_event_status_chip


class CategoryFilter(admin.SimpleListFilter):
    """Filtro sidebar per categoria negli eventi (query diretta sulla vista v_categorie)."""
    title = 'Categoria'
    parameter_name = 'categoria'

    def lookups(self, request, model_admin):
        """Restituisce le categorie disponibili dalla vista PostgreSQL."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT categoria, categoria FROM events_data.v_categorie ORDER BY categoria")
            return cursor.fetchall()

    def queryset(self, request, queryset):
        """Filtra gli eventi che contengono la categoria selezionata nel campo JSON."""
        if self.value():
            return queryset.filter(category__contains=[self.value()])
        return queryset


@admin.register(ScrapingCategory)
class ScrapingCategoryAdmin(ModelAdmin):
    """Admin per le categorie aggregate dallo scraping (vista PostgreSQL, sola lettura)."""
    list_display = ['categoria', 'count']
    ordering = ['categoria']


@admin.register(ScrapingLocation)
class ScrapingLocationAdmin(ModelAdmin):
    """Admin per le location aggregate con dettaglio eventi correlati."""
    list_display = ['location_name', 'city', 'total_count']
    list_display_links = ['location_name']
    search_fields = ['location_name', 'city']
    ordering = ['-count']

    class Media:
        css = {
            'all': ('events/css/admin_custom.css',)
        }

    readonly_fields = ['location_name', 'city', 'count', 'total_count', 'related_events']

    def total_count(self, obj):
        """Conteggio totale degli eventi per questa location."""
        return obj.count
    total_count.short_description = "Totale"
    total_count.admin_order_field = 'count'

    fieldsets = (
        (None, {
            'fields': ('location_name', ('city', 'total_count')),
        }),
        ('Eventi in questa location', {
            'fields': ('related_events',),
            'classes': ['wide'],
        }),
    )

    def related_events(self, obj):
        """Tabella degli eventi staging associati a questa location con chip stato e date italiane."""
        from events.models import StagingEvent

        events = StagingEvent.objects.filter(location_name=obj.location_name)
        if obj.city:
            events = events.filter(city=obj.city)
        events = events.order_by('-date_start')[:50]

        if not events:
            return mark_safe('<p style="color:#6b7280;">Nessun evento trovato.</p>')

        rows = []
        for e in events:
            url = f'/admin/events/stagingevent/{e.pk}/change/'
            link = format_html(
                '<a href="{}" style="color:#7c3aed;font-weight:500;">{}</a>', url, e.title
            )
            status = render_event_status_chip(e.date_start, e.date_end)
            date_end = format_date_italian(e.date_end)
            created_at = format_datetime_italian(e.loaded_at)

            rows.append(format_html(
                '<tr>'
                '<td style="padding:0.5rem 0.75rem;border-bottom:1px solid #e5e7eb;">{}</td>'
                '<td style="padding:0.5rem 0.75rem;border-bottom:1px solid #e5e7eb;">{}</td>'
                '<td style="padding:0.5rem 0.75rem;border-bottom:1px solid #e5e7eb;">{}</td>'
                '<td style="padding:0.5rem 0.75rem;border-bottom:1px solid #e5e7eb;">{}</td>'
                '<td style="padding:0.5rem 0.75rem;border-bottom:1px solid #e5e7eb;">{}</td>'
                '</tr>',
                link, created_at, e.source, status, date_end,
            ))

        header = (
            '<table style="width:100%;border-collapse:collapse;font-size:0.875rem;">'
            '<thead><tr style="background:#f9fafb;">'
            '<th style="padding:0.5rem 0.75rem;text-align:left;font-weight:600;color:#374151;border-bottom:2px solid #e5e7eb;">Titolo</th>'
            '<th style="padding:0.5rem 0.75rem;text-align:left;font-weight:600;color:#374151;border-bottom:2px solid #e5e7eb;">Creato il</th>'
            '<th style="padding:0.5rem 0.75rem;text-align:left;font-weight:600;color:#374151;border-bottom:2px solid #e5e7eb;">Source</th>'
            '<th style="padding:0.5rem 0.75rem;text-align:left;font-weight:600;color:#374151;border-bottom:2px solid #e5e7eb;">Stato</th>'
            '<th style="padding:0.5rem 0.75rem;text-align:left;font-weight:600;color:#374151;border-bottom:2px solid #e5e7eb;">Data Fine</th>'
            '</tr></thead><tbody>'
        )
        return mark_safe(header + ''.join([str(r) for r in rows]) + '</tbody></table>')
    related_events.short_description = "Eventi"
