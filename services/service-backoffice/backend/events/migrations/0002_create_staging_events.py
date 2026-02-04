from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE SCHEMA IF NOT EXISTS events_data;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="""
                CREATE TABLE IF NOT EXISTS events_data.staging_events (
                    id BIGSERIAL PRIMARY KEY,
                    uuid VARCHAR(16) NOT NULL,
                    content_hash VARCHAR(16),
                    source VARCHAR(50) NOT NULL,
                    url TEXT,
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT[],
                    image_url TEXT,
                    city VARCHAR(100),
                    location_name VARCHAR(255),
                    location_address TEXT,
                    price TEXT,
                    website TEXT,
                    date_start DATE,
                    date_end DATE,
                    time_start TIME,
                    time_end TIME,
                    time_info TEXT,
                    schedule TEXT,
                    weekdays TEXT,
                    raw_data JSONB,
                    scraped_at TIMESTAMPTZ,
                    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """,
            reverse_sql="DROP TABLE IF EXISTS events_data.staging_events;",
        ),
    ]
