"""
Configurazione admin per i modelli di scraping (categorie e location aggregate).
"""
import json
import logging

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
    list_display = ['location_name', 'city_name', 'total_count']
    list_display_links = ['location_name']
    search_fields = ['location_name', 'city_name']
    ordering = ['-count']

    class Media:
        css = {
            'all': ('events/css/admin_custom.css',)
        }

    readonly_fields = ['location_name', 'city_name', 'count', 'total_count', 'related_events']

    def total_count(self, obj):
        """Conteggio totale degli eventi per questa location."""
        return obj.count
    total_count.short_description = "Totale"
    total_count.admin_order_field = 'count'

    fieldsets = (
        (None, {
            'fields': ('location_name', ('city_name', 'total_count')),
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
        if obj.city_name:
            events = events.filter(city_name=obj.city_name)
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

    # Mappa città → dominio per city_today (importata dallo spider)
    CITY_TODAY_CITIES = {
        "milano": {"domain": "www.milanotoday.it", "name": "Milano"},
        "torino": {"domain": "www.torinotoday.it", "name": "Torino"},
        "genova": {"domain": "www.genovatoday.it", "name": "Genova"},
        "venezia": {"domain": "www.veneziatoday.it", "name": "Venezia"},
        "bologna": {"domain": "www.bolognatoday.it", "name": "Bologna"},
        "verona": {"domain": "www.veronasera.it", "name": "Verona"},
        "treviso": {"domain": "www.trevisotoday.it", "name": "Treviso"},
        "trento": {"domain": "www.trentotoday.it", "name": "Trento"},
        "udine": {"domain": "www.udinetoday.it", "name": "Udine"},
        "pordenone": {"domain": "www.pordenonetoday.it", "name": "Pordenone"},
        "vicenza": {"domain": "www.vicenzatoday.it", "name": "Vicenza"},
        "padova": {"domain": "www.padovatoday.it", "name": "Padova"},
        "monza": {"domain": "www.monzatoday.it", "name": "Monza"},
        "lecco": {"domain": "www.leccotoday.it", "name": "Lecco"},
        "sondrio": {"domain": "www.sondriotoday.it", "name": "Sondrio"},
        "novara": {"domain": "www.novaratoday.it", "name": "Novara"},
        "brescia": {"domain": "www.bresciatoday.it", "name": "Brescia"},
        "parma": {"domain": "www.parmatoday.it", "name": "Parma"},
        "rimini": {"domain": "www.riminitoday.it", "name": "Rimini"},
        "ravenna": {"domain": "www.ravennatoday.it", "name": "Ravenna"},
        "forli": {"domain": "www.forlitoday.it", "name": "Forlì"},
        "cesena": {"domain": "www.cesenatoday.it", "name": "Cesena"},
        "como": {"domain": "www.quicomo.it", "name": "Como"},
        "piacenza": {"domain": "www.ilpiacenza.it", "name": "Piacenza"},
        "trieste": {"domain": "www.triesteprima.it", "name": "Trieste"},
        "roma": {"domain": "www.romatoday.it", "name": "Roma"},
        "firenze": {"domain": "www.firenzetoday.it", "name": "Firenze"},
        "pisa": {"domain": "www.pisatoday.it", "name": "Pisa"},
        "livorno": {"domain": "www.livornotoday.it", "name": "Livorno"},
        "perugia": {"domain": "www.perugiatoday.it", "name": "Perugia"},
        "terni": {"domain": "www.ternitoday.it", "name": "Terni"},
        "ancona": {"domain": "www.anconatoday.it", "name": "Ancona"},
        "latina": {"domain": "www.latinatoday.it", "name": "Latina"},
        "frosinone": {"domain": "www.frosinonetoday.it", "name": "Frosinone"},
        "viterbo": {"domain": "www.viterbotoday.it", "name": "Viterbo"},
        "arezzo": {"domain": "www.arezzonotizie.it", "name": "Arezzo"},
        "pescara": {"domain": "www.ilpescara.it", "name": "Pescara"},
        "napoli": {"domain": "www.napolitoday.it", "name": "Napoli"},
        "palermo": {"domain": "www.palermotoday.it", "name": "Palermo"},
        "catania": {"domain": "www.cataniatoday.it", "name": "Catania"},
        "messina": {"domain": "www.messinatoday.it", "name": "Messina"},
        "bari": {"domain": "www.baritoday.it", "name": "Bari"},
        "foggia": {"domain": "www.foggiatoday.it", "name": "Foggia"},
        "salerno": {"domain": "www.salernotoday.it", "name": "Salerno"},
        "avellino": {"domain": "www.avellinotoday.it", "name": "Avellino"},
        "reggio-calabria": {"domain": "www.reggiotoday.it", "name": "Reggio Calabria"},
        "lecce": {"domain": "www.lecceprima.it", "name": "Lecce"},
        "brindisi": {"domain": "www.brindisireport.it", "name": "Brindisi"},
        "agrigento": {"domain": "www.agrigentonotizie.it", "name": "Agrigento"},
        "caserta": {"domain": "www.casertanews.it", "name": "Caserta"},
    }

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
        return mark_safe(f'''
            <div style="display:flex;align-items:center;gap:0.75rem;flex-wrap:wrap;">
                <button type="button" id="trigger-dag-btn" onclick="triggerDag({obj.pk})"
                    style="padding:0.5rem 1.25rem;background:#16a34a;color:#fff;border:none;
                    border-radius:0.375rem;cursor:pointer;font-size:0.85rem;font-weight:600;
                    display:inline-flex;align-items:center;gap:0.4rem;"
                    onmouseover="this.style.background='#15803d'"
                    onmouseout="this.style.background='#16a34a'">
                    <span class="material-symbols-outlined" style="font-size:1.1rem;">play_arrow</span>
                    Avvia Scraping
                </button>
                <span id="trigger-dag-status" style="font-size:0.85rem;color:#6b7280;"></span>
            </div>
            <script>
            function triggerDag(websiteId) {{
                var btn = document.getElementById("trigger-dag-btn");
                var status = document.getElementById("trigger-dag-status");
                btn.disabled = true;
                btn.style.opacity = "0.6";
                btn.style.cursor = "wait";
                status.textContent = "Avvio in corso...";
                status.style.color = "#16a34a";

                fetch("/admin/scraping/scrapingwebsite/" + websiteId + "/trigger-dag/", {{
                    method: "POST",
                    headers: {{
                        "Content-Type": "application/json",
                        "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,
                    }},
                }})
                .then(function(r) {{ return r.json().then(function(d) {{ return {{ok: r.ok, data: d}}; }}); }})
                .then(function(res) {{
                    if (res.ok) {{
                        status.innerHTML = 'DAG avviato: <a href="https://airflow.127.0.0.1.nip.io/dags/etl_events_daily/grid" target="_blank" style="color:#16a34a;text-decoration:underline;">' + res.data.dag_run_id + '</a>';
                        status.style.color = "#16a34a";
                    }} else {{
                        status.textContent = "Errore: " + (res.data.error || "sconosciuto");
                        status.style.color = "#dc2626";
                    }}
                    btn.disabled = false;
                    btn.style.opacity = "1";
                    btn.style.cursor = "pointer";
                }})
                .catch(function(e) {{
                    status.textContent = "Errore: " + e.message;
                    status.style.color = "#dc2626";
                    btn.disabled = false;
                    btn.style.opacity = "1";
                    btn.style.cursor = "pointer";
                }});
            }}
            </script>
        ''')
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
