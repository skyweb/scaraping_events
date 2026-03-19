"""
Data migration: aggiorna CmsType choices e aggiunge tutti gli spider
dei portali turistici regionali e delle città.
"""
from django.db import migrations, models


NEW_WEBSITES = [
    # Portali turistici città
    {
        'name': 'Turismo Torino',
        'source_url': 'https://turismotorino.org/it/visita/eventi',
        'spider_name': 'turismo_torino',
        'cms': 'directus',
        'notes': 'API MeiliSearch (listing) + Directus REST (dettaglio). Dati ricchi con traduzioni e geo.',
    },
    {
        'name': 'YesMilano',
        'source_url': 'https://www.yesmilano.it/eventi/tutti-gli-eventi',
        'spider_name': 'yes_milano',
        'cms': 'drupal',
        'notes': 'Drupal 10, paginazione ?page=N. Date via <time datetime>.',
    },
    {
        'name': 'Venezia Unica',
        'source_url': 'https://www.veneziaunica.it/it/cosa-fare-a-venezia/eventi',
        'spider_name': 'venezia_unica',
        'cms': 'strapi',
        'notes': 'API Strapi REST pubblica senza auth. Populate relazioni (immagini, categorie, POI).',
    },
    {
        'name': 'Feel Florence',
        'source_url': 'https://www.feelflorence.it/it/eventi',
        'spider_name': 'feel_florence',
        'cms': 'drupal',
        'notes': 'Drupal 10, paginazione ?page=N. Appointments con date, prezzi, POI.',
    },
    {
        'name': 'Turismo Roma',
        'source_url': 'https://www.turismoroma.it/it/tipo-evento/manifestazioni',
        'spider_name': 'turismo_roma',
        'cms': 'drupal',
        'notes': 'Drupal 7. 6 categorie (manifestazioni, mostre, musica, teatro, danza, sport). Date in italiano, coordinate WKT.',
    },
    {
        'name': 'Visit Naples',
        'source_url': 'https://www.visitnaples.eu/napoletanita/scopri-napoli',
        'spider_name': 'visit_naples',
        'cms': 'custom',
        'notes': 'CMS custom marketing-italia.eu con API JSON proprietarie. Contenuti editoriali su eventi.',
    },
    # Portali turistici regionali
    {
        'name': 'Love VdA (Valle d\'Aosta)',
        'source_url': 'https://www.lovevda.it/it/eventi/ricerca-generale',
        'spider_name': 'love_vda',
        'cms': 'orchard',
        'notes': 'Orchard CMS (ASP.NET). Paginazione server-side. Date in italiano.',
    },
    {
        'name': 'Visit Trentino',
        'source_url': 'https://www.visittrentino.info/it/guida/cosa-fare/eventi',
        'spider_name': 'visit_trentino',
        'cms': 'pimcore',
        'notes': 'Pimcore con AJAX JSON (?page=N&ajax=1&json=1). JSON-LD Event nel dettaglio.',
    },
    {
        'name': 'Südtirol.info (Alto Adige)',
        'source_url': 'https://www.suedtirol.info/it/it/esperienze-eventi/eventi-alto-adige',
        'spider_name': 'suedtirol',
        'cms': 'aem',
        'notes': 'Adobe AEM + Algolia. Card SSR nel listing, JSON-LD Event nel dettaglio.',
    },
    {
        'name': 'Veneto.eu',
        'source_url': 'https://www.veneto.eu/it/eventi',
        'spider_name': 'veneto_eu',
        'cms': 'api_rest',
        'notes': 'API REST pubblica api.veneto.eu/events. Dati completi: date ISO, coordinate, contatti.',
    },
    {
        'name': 'Turismo FVG (Friuli Venezia Giulia)',
        'source_url': 'https://www.turismofvg.it/eventi',
        'spider_name': 'turismo_fvg',
        'cms': 'custom',
        'notes': 'CMS Ikon Author. Paginazione SSR ?page=N. Date in italiano nel dettaglio.',
    },
    {
        'name': 'Visit Tuscany (Toscana)',
        'source_url': 'https://www.visittuscany.com/it/eventi/',
        'spider_name': 'visit_tuscany',
        'cms': 'api_graphql',
        'notes': 'OpenCMS con GraphQL endpoint /graphql. Query allAssets per eventi paginati.',
    },
    {
        'name': 'Umbria Tourism',
        'source_url': 'https://www.umbriatourism.it/it/eventi',
        'spider_name': 'umbria_tourism',
        'cms': 'liferay',
        'notes': 'Liferay DXP con SennaJS SPA. Eventi parziali da SSR, AJAX portlet per ricerca.',
    },
    {
        'name': 'Let\'s Marche',
        'source_url': 'https://letsmarche.it/eventi',
        'spider_name': 'lets_marche',
        'cms': 'liferay',
        'notes': 'Liferay DXP. Paginazione SSR con parametri portlet Liferay.',
    },
    {
        'name': 'Visit Lazio',
        'source_url': 'https://www.visitlazio.com/eventi/',
        'spider_name': 'visit_lazio',
        'cms': 'wordpress',
        'notes': 'WordPress + Modern Events Calendar (MEC) plugin. Slider + calendario.',
    },
    {
        'name': 'Abruzzo Turismo',
        'source_url': 'https://www.abruzzoturismo.it/it/eventi',
        'spider_name': 'abruzzo_turismo',
        'cms': 'drupal',
        'notes': 'Drupal 9 + Bootstrap Italia. Paginazione ?page=N. Mappa Leaflet.',
    },
    {
        'name': 'Visit Molise',
        'source_url': 'https://www.visitmolise.eu/eventi',
        'spider_name': 'visit_molise',
        'cms': 'liferay',
        'notes': 'Liferay DXP + Vue.js SPA. API JSON via CloudFront CDN.',
    },
    {
        'name': 'inCampania',
        'source_url': 'https://incampania.com/eventi/',
        'spider_name': 'in_campania',
        'cms': 'wordpress',
        'notes': 'WordPress con tema custom kwpress-tc. Paginazione /eventi/page/N/.',
    },
    {
        'name': 'Viaggiare in Puglia',
        'source_url': 'https://viaggiareinpuglia.it/it/eventi',
        'spider_name': 'viaggiare_in_puglia',
        'cms': 'angular_spa',
        'notes': 'Angular SPA senza API pubblica. Scraping SSR best-effort, potrebbe richiedere browser headless.',
    },
    {
        'name': 'Basilicata Turistica',
        'source_url': 'https://www.basilicataturistica.it/eventi/',
        'spider_name': 'basilicata_turistica',
        'cms': 'wordpress',
        'notes': 'WordPress + Events Manager plugin. Griglia AJAX eventi.',
    },
    {
        'name': 'Visit Sicily (Sicilia)',
        'source_url': 'https://www.visitsicily.info/evento-new/',
        'spider_name': 'visit_sicily',
        'cms': 'wordpress',
        'notes': 'WordPress con WP REST API attiva. CPT evento-new + ACF + taxonomy luogo.',
    },
    {
        'name': 'Sardegna Turismo',
        'source_url': 'https://www.sardegnaturismo.it/it/eventi',
        'spider_name': 'sardegna_turismo',
        'cms': 'drupal',
        'notes': 'Drupal 7. Views AJAX (Load More). Date ISO in span[content]. RDFa schema:Event.',
    },
]


def add_websites(apps, schema_editor):
    ScrapingWebsite = apps.get_model('scraping', 'ScrapingWebsite')
    for data in NEW_WEBSITES:
        ScrapingWebsite.objects.update_or_create(
            spider_name=data['spider_name'],
            defaults={k: v for k, v in data.items() if k != 'spider_name'},
        )


def remove_websites(apps, schema_editor):
    ScrapingWebsite = apps.get_model('scraping', 'ScrapingWebsite')
    ScrapingWebsite.objects.filter(
        spider_name__in=[w['spider_name'] for w in NEW_WEBSITES]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('scraping', '0005_add_initial_websites'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scrapingwebsite',
            name='cms',
            field=models.CharField(
                choices=[
                    ('drupal', 'Drupal'), ('wordpress', 'WordPress'), ('custom', 'Custom'),
                    ('api_rest', 'API REST'), ('api_graphql', 'API GraphQL'),
                    ('liferay', 'Liferay'), ('strapi', 'Strapi'), ('directus', 'Directus'),
                    ('angular_spa', 'Angular SPA'), ('aem', 'Adobe AEM'),
                    ('orchard', 'Orchard CMS'), ('pimcore', 'Pimcore'),
                ],
                default='custom', max_length=20, verbose_name='CMS',
            ),
        ),
        migrations.RunPython(add_websites, reverse_code=remove_websites),
    ]
