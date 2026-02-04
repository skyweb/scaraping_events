from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0004_alter_productionevent_options_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE events_data.staging_events
                    ADD COLUMN IF NOT EXISTS time_start TIME,
                    ADD COLUMN IF NOT EXISTS time_end TIME,
                    ADD COLUMN IF NOT EXISTS time_info TEXT,
                    ADD COLUMN IF NOT EXISTS schedule TEXT,
                    ADD COLUMN IF NOT EXISTS weekdays TEXT,
                    ADD COLUMN IF NOT EXISTS loaded_at TIMESTAMPTZ DEFAULT NOW();
            """,
            reverse_sql="""
                ALTER TABLE events_data.staging_events
                    DROP COLUMN IF EXISTS time_start,
                    DROP COLUMN IF EXISTS time_end,
                    DROP COLUMN IF EXISTS time_info,
                    DROP COLUMN IF EXISTS schedule,
                    DROP COLUMN IF EXISTS weekdays,
                    DROP COLUMN IF EXISTS loaded_at;
            """,
        ),
    ]
