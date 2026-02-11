from django.contrib import admin
from django.db import connection
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin
from .models import ScrapingCategoria, ScrapingLocation


class CategoriaFilter(admin.SimpleListFilter):
    """Filtro per categoria negli eventi"""
    title = 'Categoria'
    parameter_name = 'categoria'

    def lookups(self, request, model_admin):
        with connection.cursor() as cursor:
            cursor.execute("SELECT categoria, categoria FROM events_data.v_categorie ORDER BY categoria")
            return cursor.fetchall()

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(category__contains=[self.value()])
        return queryset


@admin.register(ScrapingCategoria)
class ScrapingCategoriaAdmin(ModelAdmin):
    list_display = ['categoria', 'count']
    ordering = ['categoria']


@admin.register(ScrapingLocation)
class ScrapingLocationAdmin(ModelAdmin):
    list_display = ['location_name', 'city', 'totale']
    list_display_links = ['location_name']
    search_fields = ['location_name', 'city']
    ordering = ['-count']

    class Media:
        css = {
            'all': ('events/css/admin_custom.css',)
        }

    readonly_fields = ['location_name', 'city', 'count', 'totale', 'eventi_correlati']

    def totale(self, obj):
        return obj.count
    totale.short_description = "Totale"
    totale.admin_order_field = 'count'

    fieldsets = (
        (None, {
            'fields': ('location_name', ('city', 'totale')),
        }),
        ('Eventi in questa location', {
            'fields': ('eventi_correlati',),
            'classes': ['wide'],
        }),
    )

    def eventi_correlati(self, obj):
        """Tabella degli eventi staging associati a questa location."""
        from events.models import StagingEvent

        eventi = StagingEvent.objects.filter(location_name=obj.location_name)
        if obj.city:
            eventi = eventi.filter(city=obj.city)
        eventi = eventi.order_by('-date_start')[:50]

        if not eventi:
            return mark_safe('<p style="color:#6b7280;">Nessun evento trovato.</p>')

        today = timezone.now().date()
        rows = []
        for e in eventi:
            # Link alla scheda evento
            url = f'/admin/events/stagingevent/{e.pk}/change/'
            link = format_html('<a href="{}" style="color:#7c3aed;font-weight:500;">{}</a>', url, e.title)

            # Stato chip
            if not e.date_start:
                stato = '-'
            else:
                start = e.date_start
                end = e.date_end if e.date_end else start
                if end < today:
                    stato = format_html(
                        '<span style="display:inline-block;padding:0.15rem 0.5rem;border-radius:9999px;'
                        'font-size:0.7rem;font-weight:600;white-space:nowrap;color:#991b1b;background:#fee2e2;">Passato</span>')
                elif start <= today <= end:
                    stato = format_html(
                        '<span style="display:inline-block;padding:0.15rem 0.5rem;border-radius:9999px;'
                        'font-size:0.7rem;font-weight:600;white-space:nowrap;color:#166534;background:#dcfce7;">In corso</span>')
                else:
                    stato = format_html(
                        '<span style="display:inline-block;padding:0.15rem 0.5rem;border-radius:9999px;'
                        'font-size:0.7rem;font-weight:600;white-space:nowrap;color:#1e40af;background:#dbeafe;">Futuro</span>')

            # Data fine
            data_fine = e.date_end.strftime('%d/%m/%Y') if e.date_end else '-'

            # Data creazione
            data_creazione = timezone.localtime(e.loaded_at).strftime('%d/%m/%Y %H:%M') if e.loaded_at else '-'

            rows.append(format_html(
                '<tr>'
                '<td style="padding:0.5rem 0.75rem;border-bottom:1px solid #e5e7eb;">{}</td>'
                '<td style="padding:0.5rem 0.75rem;border-bottom:1px solid #e5e7eb;">{}</td>'
                '<td style="padding:0.5rem 0.75rem;border-bottom:1px solid #e5e7eb;">{}</td>'
                '<td style="padding:0.5rem 0.75rem;border-bottom:1px solid #e5e7eb;">{}</td>'
                '<td style="padding:0.5rem 0.75rem;border-bottom:1px solid #e5e7eb;">{}</td>'
                '</tr>',
                link, data_creazione, e.source, stato, data_fine,
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
    eventi_correlati.short_description = "Eventi"
