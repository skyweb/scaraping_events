"""
Configurazione admin per i modelli di scraping (categorie e location aggregate).
"""
import json
import logging
import os
from pathlib import Path

from django.contrib import admin
from django.db import connection
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin

logger = logging.getLogger(__name__)

from django.conf import settings
from .models import ScrapingCategory, ScrapingLocation, ScrapingWebsite
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
        from events.models import Event

        events = Event.objects.filter(location_name=obj.location_name)
        if obj.city:
            events = events.filter(city=obj.city)
        events = events.order_by('-date_start')[:50]

        if not events:
            return mark_safe('<p style="color:#6b7280;">Nessun evento trovato.</p>')

        rows = []
        for e in events:
            url = f'/admin/events/event/{e.pk}/change/'
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


@admin.register(ScrapingWebsite)
class ScrapingWebsiteAdmin(ModelAdmin):
    """Admin per i portali web scrapati con relativi spider e CMS."""
    list_display = ['name', 'spider_name', 'cms_badge', 'source_url_link', 'status_chip']
    list_display_links = ['name']
    list_filter = ['cms', 'is_active']
    search_fields = ['name', 'spider_name', 'source_url']
    ordering = ['name']
    readonly_fields = ['trigger_dag_button', 'cities_detail']
    actions = ['trigger_scraping']

    fieldsets = (
        (None, {
            'fields': ('name', 'source_url', 'is_active'),
        }),
        ('Spider', {
            'fields': ('spider_name', 'cms', 'trigger_dag_button'),
        }),
        ('Città coperte', {
            'fields': ('cities_detail',),
            'classes': ['wide', 'collapse'],
        }),
        ('Note', {
            'fields': ('notes',),
            'classes': ['wide'],
        }),
    )

    # Mappa città → dominio per city_today (caricata da file JSON)
    _CITIES_PATH = Path(__file__).parent / "data" / "city_today_cities.json"
    CITY_TODAY_CITIES: dict[str, dict[str, str]] = json.loads(_CITIES_PATH.read_text(encoding="utf-8"))

    def cities_detail(self, obj):
        """Tabella delle città coperte dallo spider (solo per city_today)."""
        if obj.spider_name != 'city_today':
            return mark_safe('<span style="color:#6b7280;font-size:0.85rem;">Questo spider non ha sotto-città.</span>')

        rows = []
        for slug, info in self.CITY_TODAY_CITIES.items():
            domain = info["domain"]
            url = f"https://{domain}/eventi/"
            rows.append(format_html(
                '<tr>'
                '<td style="padding:0.35rem 0.75rem;border-bottom:1px solid #e5e7eb;">{}</td>'
                '<td style="padding:0.35rem 0.75rem;border-bottom:1px solid #e5e7eb;font-family:monospace;font-size:0.8rem;">{}</td>'
                '<td style="padding:0.35rem 0.75rem;border-bottom:1px solid #e5e7eb;">'
                '<a href="{}" target="_blank" rel="noopener" style="color:#7c3aed;">{}</a></td>'
                '</tr>',
                info["name"], slug, url, domain,
            ))

        header = (
            '<table style="width:100%;border-collapse:collapse;font-size:0.875rem;">'
            '<thead><tr style="background:#f9fafb;">'
            '<th style="padding:0.4rem 0.75rem;text-align:left;font-weight:600;color:#374151;border-bottom:2px solid #e5e7eb;">Città</th>'
            '<th style="padding:0.4rem 0.75rem;text-align:left;font-weight:600;color:#374151;border-bottom:2px solid #e5e7eb;">Slug</th>'
            '<th style="padding:0.4rem 0.75rem;text-align:left;font-weight:600;color:#374151;border-bottom:2px solid #e5e7eb;">Dominio</th>'
            '</tr></thead><tbody>'
        )
        count = len(self.CITY_TODAY_CITIES)
        return mark_safe(
            f'<p style="margin-bottom:0.5rem;color:#374151;font-weight:600;">{count} città coperte</p>'
            + header + ''.join([str(r) for r in rows]) + '</tbody></table>'
        )
    cities_detail.short_description = "Città coperte"

    DAG_ID = 'etl_events_daily'

    def _trigger_dag(self, spider_name):
        """Chiama Airflow REST API per triggerare il DAG con lo spider specificato."""
        import requests
        url = f'{settings.AIRFLOW_API_URL}/dags/{self.DAG_ID}/dagRuns'
        response = requests.post(
            url,
            json={'conf': {'city': spider_name}},
            auth=(
                settings.AIRFLOW_API_USER,
                settings.AIRFLOW_API_PASSWORD,
            ),
            headers={'Content-Type': 'application/json'},
            timeout=10,
        )
        return response

    def trigger_dag_button(self, obj):
        """Pulsante per avviare il DAG Airflow collegato allo spider."""
        if not obj.pk:
            return "-"
        from django.template.loader import render_to_string
        domain = os.environ.get("DOMAIN", "127.0.0.1.nip.io")
        html = render_to_string('admin/scraping/trigger_dag_button.html', {
            'pk': obj.pk,
            'airflow_grid_url': f"https://airflow.{domain}/dags/{self.DAG_ID}/grid",
        })
        return mark_safe(html)
    trigger_dag_button.short_description = "Avvia Scraping"

    def get_urls(self):
        """Aggiunge URL custom per il trigger DAG."""
        from django.urls import path
        urls = super().get_urls()
        custom = [
            path(
                '<int:pk>/trigger-dag/',
                self.admin_site.admin_view(self.trigger_dag_view),
                name='scrapingwebsite-trigger-dag',
            ),
        ]
        return custom + urls

    def trigger_dag_view(self, request, pk):
        """Endpoint admin per triggerare il DAG Airflow."""
        from django.http import JsonResponse

        if request.method != 'POST':
            return JsonResponse({'error': 'Metodo non consentito'}, status=405)

        try:
            obj = ScrapingWebsite.objects.get(pk=pk)
        except ScrapingWebsite.DoesNotExist:
            return JsonResponse({'error': 'Website non trovato'}, status=404)

        try:
            response = self._trigger_dag(obj.spider_name)
            if response.status_code in (200, 201):
                result = response.json()
                dag_run_id = result.get('dag_run_id', 'unknown')
                logger.info(f"DAG triggerato per spider {obj.spider_name}: {dag_run_id}")
                return JsonResponse({'ok': True, 'dag_run_id': dag_run_id, 'spider': obj.spider_name})
            else:
                return JsonResponse({'error': f'Airflow: {response.status_code} - {response.text}'}, status=502)
        except Exception as e:
            logger.exception(f"Errore trigger DAG per {obj.spider_name}")
            return JsonResponse({'error': str(e)}, status=500)

    @admin.action(description="Avvia scraping per i siti selezionati")
    def trigger_scraping(self, request, queryset):
        """Azione bulk per triggerare il DAG per più siti."""
        success = 0
        errors = []
        for website in queryset.filter(is_active=True):
            try:
                response = self._trigger_dag(website.spider_name)
                if response.status_code in (200, 201):
                    success += 1
                else:
                    errors.append(f"{website.name}: {response.status_code}")
            except Exception as e:
                errors.append(f"{website.name}: {e}")

        msg = f"Scraping avviato per {success} siti."
        if errors:
            msg += f" Errori: {', '.join(errors)}"
        self.message_user(request, msg)

    def cms_badge(self, obj):
        """Badge colorato per il tipo di CMS."""
        colors = {
            'drupal': ('#0678be', '#fff'),
            'wordpress': ('#21759b', '#fff'),
            'api_rest': ('#16a34a', '#fff'),
            'api_graphql': ('#e535ab', '#fff'),
            'strapi': ('#4945ff', '#fff'),
            'directus': ('#6644ff', '#fff'),
            'liferay': ('#0b5fff', '#fff'),
            'angular_spa': ('#dd0031', '#fff'),
            'aem': ('#eb1000', '#fff'),
            'orchard': ('#3f6833', '#fff'),
            'pimcore': ('#6428b4', '#fff'),
            'custom': ('#6b7280', '#fff'),
        }
        bg, fg = colors.get(obj.cms, ('#6b7280', '#fff'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;border-radius:9999px;'
            'font-size:0.75rem;font-weight:600;">{}</span>',
            bg, fg, obj.get_cms_display(),
        )
    cms_badge.short_description = 'CMS'
    cms_badge.admin_order_field = 'cms'

    def source_url_link(self, obj):
        """URL del sito come link cliccabile."""
        return format_html(
            '<a href="{}" target="_blank" rel="noopener" style="color:#7c3aed;">{}</a>',
            obj.source_url,
            obj.source_url,
        )
    source_url_link.short_description = 'URL'

    def status_chip(self, obj):
        """Chip colorato per lo stato attivo/inattivo."""
        if obj.is_active:
            return format_html(
                '<span style="background:#dcfce7;color:#16a34a;padding:2px 10px;'
                'border-radius:9999px;font-size:0.75rem;font-weight:600;">Attivo</span>'
            )
        return format_html(
            '<span style="background:#fee2e2;color:#dc2626;padding:2px 10px;'
            'border-radius:9999px;font-size:0.75rem;font-weight:600;">Inattivo</span>'
        )
    status_chip.short_description = 'Stato'
    status_chip.admin_order_field = 'is_active'
