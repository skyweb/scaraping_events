from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0012_add_batch_file'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='stagingevent',
            name='section',
        ),
    ]
