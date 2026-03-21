from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api_consumers", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="apiconsumer",
            name="api_key",
            field=models.CharField(
                blank=True,
                help_text="Generata automaticamente alla creazione",
                max_length=255,
                null=True,
                unique=True,
            ),
        ),
    ]
