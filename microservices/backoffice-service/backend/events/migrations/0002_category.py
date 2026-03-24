from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='Nome')),
            ],
            options={
                'verbose_name': 'Categoria',
                'verbose_name_plural': 'Categorie',
                'db_table': 'events_data"."categories',
                'ordering': ['name'],
            },
        ),
    ]
