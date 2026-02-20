from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scraping', '0003_scrapingcategory_delete_scrapingcategoria'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScrapingWebsite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Nome portale')),
                ('source_url', models.URLField(max_length=500, verbose_name='URL base')),
                ('spider_name', models.CharField(
                    help_text='Nome del file spider Scrapy (es: in_lombardia)',
                    max_length=100,
                    unique=True,
                    verbose_name='Nome spider',
                )),
                ('cms', models.CharField(
                    choices=[
                        ('drupal', 'Drupal'),
                        ('wordpress', 'WordPress'),
                        ('custom', 'Custom'),
                        ('api_rest', 'API REST'),
                    ],
                    default='custom',
                    max_length=20,
                    verbose_name='CMS',
                )),
                ('is_active', models.BooleanField(default=True, verbose_name='Attivo')),
                ('notes', models.TextField(blank=True, verbose_name='Note')),
            ],
            options={
                'verbose_name': 'Website',
                'verbose_name_plural': 'Websites',
                'db_table': 'scraping_website',
                'ordering': ['name'],
            },
        ),
    ]
