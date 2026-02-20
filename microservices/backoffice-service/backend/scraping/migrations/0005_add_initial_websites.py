"""
Data migration: popola ScrapingWebsite con tutti gli spider presenti
nel microservizio scraping-service.
"""
from django.db import migrations


WEBSITES = [
    {
        'name': 'Artribune',
        'source_url': 'https://www.artribune.com/eventi/',
        'spider_name': 'artribune',
        'cms': 'wordpress',
        'notes': 'Magazine arte e cultura. Usa WordPress REST API (wp-json/wp/v2/event).',
    },
    {
        'name': 'Rete Today.it (50+ città)',
        'source_url': 'https://www.milanotoday.it/eventi/',
        'spider_name': 'city_today',
        'cms': 'custom',
        'notes': (
            'Rete di portali locali: MilanoToday, RomaToday, BolognaToday, etc. '
            'Parametri: cities (lista separata da virgola), periodo.'
        ),
    },
    {
        'name': 'In Lombardia',
        'source_url': 'https://www.in-lombardia.it/it/eventi',
        'spider_name': 'in_lombardia',
        'cms': 'drupal',
        'notes': 'Portale eventi Lombardia. Usa JSON-LD Schema.org @type:Event su ogni pagina dettaglio.',
    },
    {
        'name': 'La Mia Liguria',
        'source_url': 'https://lamialiguria.it/vivi-la-liguria/liguria-eventi/',
        'spider_name': 'la_mia_liguria',
        'cms': 'wordpress',
        'notes': 'Portale turistico Liguria. JSON-LD WebPage + HTML parsing per date e location.',
    },
    {
        'name': 'Zero.eu',
        'source_url': 'https://zero.eu/',
        'spider_name': 'zero_eu',
        'cms': 'wordpress',
        'notes': (
            'Portale eventi culturali italiani. Usa WordPress REST API (wp-json). '
            'Parametro: city (milano, roma, bologna, torino, firenze, venezia, napoli).'
        ),
    },
    {
        'name': 'Puglia Culture',
        'source_url': 'https://www.pugliaculture.it/ricerca-eventi',
        'spider_name': 'puglia_culture',
        'cms': 'wordpress',
        'notes': (
            'Portale eventi culturali Puglia. '
            'WP REST API per listing + HTML scraping Elementor per dettagli. '
            'Totale ~35 pagine API (3500 eventi).'
        ),
    },
]


def add_websites(apps, schema_editor):
    ScrapingWebsite = apps.get_model('scraping', 'ScrapingWebsite')
    for data in WEBSITES:
        ScrapingWebsite.objects.get_or_create(
            spider_name=data['spider_name'],
            defaults={k: v for k, v in data.items() if k != 'spider_name'},
        )


def remove_websites(apps, schema_editor):
    ScrapingWebsite = apps.get_model('scraping', 'ScrapingWebsite')
    ScrapingWebsite.objects.filter(
        spider_name__in=[w['spider_name'] for w in WEBSITES]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('scraping', '0004_scrapingwebsite'),
    ]

    operations = [
        migrations.RunPython(add_websites, reverse_code=remove_websites),
    ]
