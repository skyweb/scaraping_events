from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0014_stagingevent_uuid_unique'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='stagingevent',
            name='info_extra',
        ),
    ]
