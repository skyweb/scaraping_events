from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0013_remove_stagingevent_section'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stagingevent',
            name='uuid',
            field=models.CharField(max_length=16, unique=True),
        ),
    ]
