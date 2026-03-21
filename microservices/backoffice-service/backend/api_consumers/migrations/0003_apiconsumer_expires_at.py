from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api_consumers", "0002_alter_apiconsumer_api_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="apiconsumer",
            name="expires_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Data di scadenza. Lasciare vuoto per accesso illimitato.",
                null=True,
            ),
        ),
    ]
