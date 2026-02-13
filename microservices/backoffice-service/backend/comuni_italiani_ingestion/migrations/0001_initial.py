from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        # Crea lo schema dedicato per l'ingestion
        migrations.RunSQL(
            'CREATE SCHEMA IF NOT EXISTS comuni_italiani_ingestion;',
            reverse_sql='DROP SCHEMA IF EXISTS comuni_italiani_ingestion CASCADE;',
        ),
        migrations.CreateModel(
            name='ComuniItalianiRawData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('regione', 'Regione'), ('provincia', 'Provincia'), ('comune', 'Comune')], max_length=20)),
                ('codice_istat', models.CharField(max_length=10)),
                ('regione', models.CharField(max_length=100)),
                ('provincia', models.CharField(blank=True, max_length=100, null=True)),
                ('comune', models.CharField(blank=True, max_length=100, null=True)),
                ('raw_json', models.JSONField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'comuni_italiani_ingestion"."raw_data',
                'verbose_name': 'Raw Data',
                'verbose_name_plural': 'Raw Data',
            },
        ),
        migrations.AddIndex(
            model_name='comuniitalianirawdata',
            index=models.Index(fields=['tipo'], name='comuni_ital_tipo_idx'),
        ),
        migrations.AddIndex(
            model_name='comuniitalianirawdata',
            index=models.Index(fields=['codice_istat'], name='comuni_ital_codice__idx'),
        ),
        migrations.AddIndex(
            model_name='comuniitalianirawdata',
            index=models.Index(fields=['tipo', 'codice_istat'], name='comuni_ital_tipo_co_idx'),
        ),
    ]
